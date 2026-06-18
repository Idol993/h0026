import csv
import io
from datetime import datetime
from typing import List, Dict
from sqlalchemy.orm import Session


def get_worker_monthly_stats(db: Session) -> List[Dict]:
    from server.main import Worker, Ticket

    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)

    workers = db.query(Worker).all()
    stats = []

    for worker in workers:
        completed_tickets = db.query(Ticket).filter(
            Ticket.assigned_worker_id == worker.id,
            Ticket.status == "已完成",
            Ticket.completed_at >= month_start
        ).all()

        ticket_count = len(completed_tickets)

        if ticket_count > 0:
            total_duration = sum(t.duration or 0 for t in completed_tickets)
            avg_duration = round(total_duration / ticket_count, 2)

            ratings = [t.rating for t in completed_tickets if t.rating is not None]
            avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
        else:
            avg_duration = 0
            avg_rating = None

        stats.append({
            "worker_id": worker.id,
            "worker_name": worker.name,
            "month": f"{now.year}-{now.month:02d}",
            "completed_tickets": ticket_count,
            "avg_duration_hours": avg_duration,
            "avg_rating": avg_rating
        })

    return stats


def export_stats_csv(db: Session) -> str:
    stats = get_worker_monthly_stats(db)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "维修工ID",
        "维修工姓名",
        "统计月份",
        "本月完成工单数",
        "平均完工时长(小时)",
        "业主评价平均分"
    ])

    for item in stats:
        writer.writerow([
            item["worker_id"],
            item["worker_name"],
            item["month"],
            item["completed_tickets"],
            item["avg_duration_hours"],
            item["avg_rating"] if item["avg_rating"] is not None else "暂无评分"
        ])

    return output.getvalue()


if __name__ == "__main__":
    import sys
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    DATABASE_URL = "sqlite:///./property.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "export":
            csv_data = export_stats_csv(db)
            print(csv_data)
        else:
            import json
            stats = get_worker_monthly_stats(db)
            print(json.dumps(stats, ensure_ascii=False, indent=2))
    finally:
        db.close()
