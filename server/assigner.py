import json
from typing import Optional, List
from sqlalchemy.orm import Session

unassigned_queue: List[int] = []


def auto_assign_worker(db: Session, ticket) -> Optional[object]:
    from server.main import Worker, Ticket

    workers = db.query(Worker).all()

    matching_workers = []
    for worker in workers:
        fault_types = json.loads(worker.fault_types) if worker.fault_types else []
        if ticket.fault_type in fault_types or ticket.fault_type == "其他":
            matching_workers.append(worker)

    if not matching_workers:
        return None

    worker_load = []
    for worker in matching_workers:
        active_count = db.query(Ticket).filter(
            Ticket.assigned_worker_id == worker.id,
            Ticket.status == "维修中"
        ).count()
        worker_load.append((worker, active_count))

    worker_load.sort(key=lambda x: x[1])
    return worker_load[0][0]


def notify_worker(worker, ticket):
    print("=" * 50)
    print(f"[工单通知] 维修工：{worker.name}")
    print(f"  工单号：{ticket.ticket_no}")
    print(f"  房号：{ticket.room_number}")
    print(f"  故障类型：{ticket.fault_type}")
    print(f"  报修描述：{ticket.description}")
    print(f"  创建时间：{ticket.created_at}")
    print("=" * 50)


def send_wechat_webhook(webhook_url: str, ticket) -> bool:
    try:
        import requests
        message = f"【物业报修工单提醒】\n工单号：{ticket.ticket_no}\n房号：{ticket.room_number}\n故障类型：{ticket.fault_type}\n描述：{ticket.description}"
        data = {"msgtype": "text", "text": {"content": message}}
        response = requests.post(webhook_url, json=data)
        return response.status_code == 200
    except Exception as e:
        print(f"[企微推送失败] {e}")
        return False
