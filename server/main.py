import json
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, Field

from server.assigner import auto_assign_worker, unassigned_queue, notify_worker
from server.reports import get_worker_monthly_stats, export_stats_csv

DATABASE_URL = "sqlite:///./property.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)


class Worker(Base):
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    fault_types = Column(Text, nullable=False)

    def get_fault_types(self):
        return json.loads(self.fault_types) if self.fault_types else []


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_no = Column(String(50), unique=True, index=True, nullable=False)
    room_number = Column(String(50), index=True, nullable=False)
    description = Column(Text, nullable=False)
    fault_type = Column(String(50), index=True, nullable=False)
    status = Column(String(20), index=True, nullable=False, default="待指派")
    assigned_worker_id = Column(Integer, ForeignKey("workers.id"), nullable=True)
    assigned_worker = relationship("Worker", backref="tickets")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)
    rating = Column(Integer, nullable=True)


Base.metadata.create_all(bind=engine)


class TenantCreate(BaseModel):
    room_number: str
    name: str
    phone: str


class TenantResponse(BaseModel):
    id: int
    room_number: str
    name: str
    phone: str

    class Config:
        from_attributes = True


class WorkerCreate(BaseModel):
    name: str
    phone: str
    fault_types: List[str]


class WorkerResponse(BaseModel):
    id: int
    name: str
    phone: str
    fault_types: List[str]

    class Config:
        from_attributes = True


class TicketCreate(BaseModel):
    room_number: str
    description: str
    fault_type: str = Field(..., description="故障类型：水电/照明/门禁/其他")


class TicketAssign(BaseModel):
    worker_id: int


class TicketComplete(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="业主评分1-5星")


class TicketResponse(BaseModel):
    id: int
    ticket_no: str
    room_number: str
    description: str
    fault_type: str
    status: str
    assigned_worker_id: Optional[int] = None
    assigned_worker_name: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    rating: Optional[int] = None

    class Config:
        from_attributes = True


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_ticket_no(db: Session) -> str:
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    prefix = f"GD{date_str}"
    last_ticket = db.query(Ticket).filter(Ticket.ticket_no.like(f"{prefix}%")).order_by(Ticket.id.desc()).first()
    if last_ticket:
        seq = int(last_ticket.ticket_no[-4:]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


app = FastAPI(title="物业报修工单API服务", version="1.0.0")


@app.get("/")
def root():
    return {"message": "物业报修工单API服务", "docs": "/docs"}


@app.post("/api/tenants", response_model=TenantResponse)
def create_tenant(tenant: TenantCreate, db: Session = Depends(get_db)):
    existing = db.query(Tenant).filter(Tenant.room_number == tenant.room_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="该房号已存在")
    db_tenant = Tenant(
        room_number=tenant.room_number,
        name=tenant.name,
        phone=tenant.phone
    )
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant


@app.get("/api/tenants", response_model=List[TenantResponse])
def list_tenants(db: Session = Depends(get_db)):
    return db.query(Tenant).all()


@app.post("/api/workers", response_model=WorkerResponse)
def create_worker(worker: WorkerCreate, db: Session = Depends(get_db)):
    db_worker = Worker(
        name=worker.name,
        phone=worker.phone,
        fault_types=json.dumps(worker.fault_types, ensure_ascii=False)
    )
    db.add(db_worker)
    db.commit()
    db.refresh(db_worker)
    result = {
        "id": db_worker.id,
        "name": db_worker.name,
        "phone": db_worker.phone,
        "fault_types": db_worker.get_fault_types()
    }
    return result


@app.get("/api/workers", response_model=List[WorkerResponse])
def list_workers(db: Session = Depends(get_db)):
    workers = db.query(Worker).all()
    result = []
    for w in workers:
        result.append({
            "id": w.id,
            "name": w.name,
            "phone": w.phone,
            "fault_types": w.get_fault_types()
        })
    return result


@app.post("/api/tickets", response_model=TicketResponse)
def create_ticket(ticket: TicketCreate, db: Session = Depends(get_db)):
    valid_types = ["水电", "照明", "门禁", "其他"]
    if ticket.fault_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"故障类型必须是: {', '.join(valid_types)}")

    ticket_no = generate_ticket_no(db)
    db_ticket = Ticket(
        ticket_no=ticket_no,
        room_number=ticket.room_number,
        description=ticket.description,
        fault_type=ticket.fault_type,
        status="待指派",
        created_at=datetime.utcnow()
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)

    worker = auto_assign_worker(db, db_ticket)
    if worker:
        db_ticket.assigned_worker_id = worker.id
        db_ticket.status = "维修中"
        db.commit()
        db.refresh(db_ticket)
        notify_worker(worker, db_ticket)
        print(f"[自动指派] 工单 {ticket_no} 已指派给维修工 {worker.name}")
    else:
        unassigned_queue.append(db_ticket.id)
        print(f"[提醒] 工单 {ticket_no} 无法自动指派，已加入待分配队列，请手动处理")

    result = {
        "id": db_ticket.id,
        "ticket_no": db_ticket.ticket_no,
        "room_number": db_ticket.room_number,
        "description": db_ticket.description,
        "fault_type": db_ticket.fault_type,
        "status": db_ticket.status,
        "assigned_worker_id": db_ticket.assigned_worker_id,
        "assigned_worker_name": db_ticket.assigned_worker.name if db_ticket.assigned_worker else None,
        "created_at": db_ticket.created_at,
        "completed_at": db_ticket.completed_at,
        "duration": db_ticket.duration,
        "rating": db_ticket.rating,
    }
    return result


@app.post("/api/tickets/{ticket_id}/assign", response_model=TicketResponse)
def assign_ticket(ticket_id: int, assign: TicketAssign, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    worker = db.query(Worker).filter(Worker.id == assign.worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="维修工不存在")

    ticket.assigned_worker_id = worker.id
    ticket.status = "维修中"
    db.commit()
    db.refresh(ticket)

    notify_worker(worker, ticket)
    print(f"[手动指派] 工单 {ticket.ticket_no} 已指派给维修工 {worker.name}")

    result = {
        "id": ticket.id,
        "ticket_no": ticket.ticket_no,
        "room_number": ticket.room_number,
        "description": ticket.description,
        "fault_type": ticket.fault_type,
        "status": ticket.status,
        "assigned_worker_id": ticket.assigned_worker_id,
        "assigned_worker_name": ticket.assigned_worker.name if ticket.assigned_worker else None,
        "created_at": ticket.created_at,
        "completed_at": ticket.completed_at,
        "duration": ticket.duration,
        "rating": ticket.rating,
    }
    return result


@app.post("/api/tickets/{ticket_id}/complete", response_model=TicketResponse)
def complete_ticket(ticket_id: int, complete: TicketComplete, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    if ticket.status == "已完成":
        raise HTTPException(status_code=400, detail="工单已完成，请勿重复操作")

    if not ticket.assigned_worker_id:
        raise HTTPException(status_code=400, detail="工单尚未指派维修工，无法完成")

    now = datetime.utcnow()
    ticket.completed_at = now
    ticket.status = "已完成"
    ticket.rating = complete.rating

    duration_seconds = (now - ticket.created_at).total_seconds()
    ticket.duration = round(duration_seconds / 3600, 2)

    db.commit()
    db.refresh(ticket)

    result = {
        "id": ticket.id,
        "ticket_no": ticket.ticket_no,
        "room_number": ticket.room_number,
        "description": ticket.description,
        "fault_type": ticket.fault_type,
        "status": ticket.status,
        "assigned_worker_id": ticket.assigned_worker_id,
        "assigned_worker_name": ticket.assigned_worker.name if ticket.assigned_worker else None,
        "created_at": ticket.created_at,
        "completed_at": ticket.completed_at,
        "duration": ticket.duration,
        "rating": ticket.rating,
    }
    return result


@app.get("/api/tickets", response_model=List[TicketResponse])
def list_tickets(
    room_number: Optional[str] = Query(None, description="按房号筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    fault_type: Optional[str] = Query(None, description="按故障类型筛选"),
    start_date: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    query = db.query(Ticket)

    if room_number:
        query = query.filter(Ticket.room_number == room_number)
    if status:
        query = query.filter(Ticket.status == status)
    if fault_type:
        query = query.filter(Ticket.fault_type == fault_type)
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Ticket.created_at >= start_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="开始日期格式错误，请使用YYYY-MM-DD")
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Ticket.created_at < end_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="结束日期格式错误，请使用YYYY-MM-DD")

    tickets = query.order_by(Ticket.created_at.desc()).all()

    result = []
    for ticket in tickets:
        result.append({
            "id": ticket.id,
            "ticket_no": ticket.ticket_no,
            "room_number": ticket.room_number,
            "description": ticket.description,
            "fault_type": ticket.fault_type,
            "status": ticket.status,
            "assigned_worker_id": ticket.assigned_worker_id,
            "assigned_worker_name": ticket.assigned_worker.name if ticket.assigned_worker else None,
            "created_at": ticket.created_at,
            "completed_at": ticket.completed_at,
            "duration": ticket.duration,
            "rating": ticket.rating,
        })
    return result


@app.get("/api/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    result = {
        "id": ticket.id,
        "ticket_no": ticket.ticket_no,
        "room_number": ticket.room_number,
        "description": ticket.description,
        "fault_type": ticket.fault_type,
        "status": ticket.status,
        "assigned_worker_id": ticket.assigned_worker_id,
        "assigned_worker_name": ticket.assigned_worker.name if ticket.assigned_worker else None,
        "created_at": ticket.created_at,
        "completed_at": ticket.completed_at,
        "duration": ticket.duration,
        "rating": ticket.rating,
    }
    return result


@app.get("/api/reports/monthly")
def monthly_report(db: Session = Depends(get_db)):
    return get_worker_monthly_stats(db)


@app.get("/api/reports/export")
def export_report(db: Session = Depends(get_db)):
    csv_data = export_stats_csv(db)

    def iter_csv():
        yield csv_data.encode("utf-8-sig")

    response = StreamingResponse(
        iter_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=worker_report_{datetime.now().strftime('%Y%m%d')}.csv"}
    )
    return response


@app.get("/api/unassigned-queue")
def get_unassigned_queue():
    return {"unassigned_count": len(unassigned_queue), "ticket_ids": unassigned_queue}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
