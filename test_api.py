import requests
import json

BASE = 'http://localhost:8000'

print('=== 创建维修工 ===')
workers = [
    {'name': '张师傅', 'phone': '13800138001', 'fault_types': ['水电', '照明']},
    {'name': '李师傅', 'phone': '13800138002', 'fault_types': ['门禁', '其他']},
]
for w in workers:
    r = requests.post(f'{BASE}/api/workers', json=w)
    print(f'创建维修工: {r.json()}')

print('\n=== 创建业主 ===')
tenants = [
    {'room_number': 'A101', 'name': '王先生', 'phone': '13900139001'},
    {'room_number': 'A202', 'name': '李女士', 'phone': '13900139002'},
]
for t in tenants:
    r = requests.post(f'{BASE}/api/tenants', json=t)
    print(f'创建业主: {r.json()}')

print('\n=== 提交报修工单 ===')
tickets = [
    {'room_number': 'A101', 'description': '厨房水管漏水', 'fault_type': '水电'},
    {'room_number': 'A202', 'description': '客厅灯不亮了', 'fault_type': '照明'},
    {'room_number': 'A101', 'description': '门禁卡刷不开门', 'fault_type': '门禁'},
]
ticket_ids = []
for t in tickets:
    r = requests.post(f'{BASE}/api/tickets', json=t)
    data = r.json()
    ticket_ids.append(data['id'])
    print(f'工单创建: 工单号={data["ticket_no"]}, 状态={data["status"]}, 指派维修工={data["assigned_worker_name"]}')

print('\n=== 查询所有工单 ===')
r = requests.get(f'{BASE}/api/tickets')
print(f'共 {len(r.json())} 条工单')

print('\n=== 按状态筛选(维修中) ===')
r = requests.get(f'{BASE}/api/tickets?status=维修中')
print(f'维修中工单: {len(r.json())} 条')

print('\n=== 按房号筛选 ===')
r = requests.get(f'{BASE}/api/tickets?room_number=A101')
print(f'A101工单: {len(r.json())} 条')

print('\n=== 手动指派工单 ===')
r = requests.post(f'{BASE}/api/tickets/{ticket_ids[2]}/assign', json={'worker_id': 1})
data = r.json()
print(f'工单 {data["ticket_no"]} 手动指派给: {data["assigned_worker_name"]}')

print('\n=== 完成第一个工单 ===')
r = requests.post(f'{BASE}/api/tickets/{ticket_ids[0]}/complete', json={'rating': 5})
data = r.json()
print(f'工单 {data["ticket_no"]} 完成, 耗时={data["duration"]}小时, 评分={data["rating"]}星')

print('\n=== 完成第二个工单 ===')
r = requests.post(f'{BASE}/api/tickets/{ticket_ids[1]}/complete', json={'rating': 4})
data = r.json()
print(f'工单 {data["ticket_no"]} 完成, 耗时={data["duration"]}小时, 评分={data["rating"]}星')

print('\n=== 本月统计报表 ===')
r = requests.get(f'{BASE}/api/reports/monthly')
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print('\n=== 测试通过！ ===')
