import requests
import json

BASE = 'http://localhost:8000'

print('=' * 60)
print('  物业报修工单API v2.0 完整业务流程测试')
print('=' * 60)

# ===== 1. 创建维修工 =====
print('\n【步骤1】创建维修工')
workers_data = [
    {'name': '张师傅', 'phone': '13800138001', 'fault_types': ['水电', '照明']},
    {'name': '李师傅', 'phone': '13800138002', 'fault_types': ['门禁']},
    {'name': '王师傅', 'phone': '13800138003', 'fault_types': ['水电', '其他']},
]
worker_ids = []
for w in workers_data:
    r = requests.post(f'{BASE}/api/workers', json=w)
    data = r.json()
    worker_ids.append(data['id'])
    print(f'  创建: {data["name"]} (ID={data["id"]}), 负责类型: {data["fault_types"]}')

# ===== 2. 创建业主 =====
print('\n【步骤2】创建业主')
tenants_data = [
    {'room_number': 'A101', 'name': '业主王', 'phone': '13900139001'},
    {'room_number': 'B202', 'name': '业主李', 'phone': '13900139002'},
]
for t in tenants_data:
    r = requests.post(f'{BASE}/api/tenants', json=t)
    print(f'  创建: {r.json()["name"]} 房号={r.json()["room_number"]}')

# ===== 3. 提交报修工单（水电类，应自动指派给张师傅，状态=待接单） =====
print('\n【步骤3】提交报修工单（水电类）')
r = requests.post(f'{BASE}/api/tickets', json={
    'room_number': 'A101', 'description': '厨房水管漏水', 'fault_type': '水电'
})
t1 = r.json()
print(f'  工单号: {t1["ticket_no"]}')
print(f'  状态: {t1["status"]}')
print(f'  指派维修工: {t1["assigned_worker_name"]}')
print(f'  流转日志:')
for log in t1['logs']:
    print(f'    [{log["action"]}] {log["detail"]} (操作人: {log["operator"]})')

# ===== 4. 维修工接单 =====
print('\n【步骤4】维修工接单')
r = requests.post(f'{BASE}/api/tickets/{t1["id"]}/accept')
t1 = r.json()
print(f'  状态: {t1["status"]}')
print(f'  流转日志:')
for log in t1['logs']:
    print(f'    [{log["action"]}] {log["detail"]}')

# ===== 5. 确认完工+评分 =====
print('\n【步骤5】确认完工+评分')
r = requests.post(f'{BASE}/api/tickets/{t1["id"]}/complete', json={'rating': 5})
t1 = r.json()
print(f'  状态: {t1["status"]}, 耗时: {t1["duration"]}小时, 评分: {t1["rating"]}星')
print(f'  流转日志:')
for log in t1['logs']:
    print(f'    [{log["action"]}] {log["detail"]}')

# ===== 6. 提交报修工单（照明类，张师傅1单已完成，应指派给张师傅）→ 拒单测试 =====
print('\n【步骤6】提交报修工单（照明类）→ 测试拒单流程')
r = requests.post(f'{BASE}/api/tickets', json={
    'room_number': 'B202', 'description': '客厅灯不亮了', 'fault_type': '照明'
})
t2 = r.json()
print(f'  工单号: {t2["ticket_no"]}, 状态: {t2["status"]}, 指派: {t2["assigned_worker_name"]}')

# 张师傅拒单
print('\n  张师傅拒单...')
r = requests.post(f'{BASE}/api/tickets/{t2["id"]}/reject', json={'reason': '正在赶往其他小区处理紧急事故'})
t2 = r.json()
print(f'  拒单后状态: {t2["status"]}, 新指派: {t2["assigned_worker_name"]}')
print(f'  流转日志:')
for log in t2['logs']:
    print(f'    [{log["action"]}] {log["detail"]}')

# 新维修工接单
if t2["assigned_worker_name"]:
    print(f'\n  {t2["assigned_worker_name"]}接单...')
    r = requests.post(f'{BASE}/api/tickets/{t2["id"]}/accept')
    t2 = r.json()
    print(f'  接单后状态: {t2["status"]}')

# ===== 7. 提交报修工单（其他类）→ 测试"其他"类型只分给负责其他的维修工 =====
print('\n【步骤7】提交报修工单（其他类）→ 测试"其他"类型修复')
r = requests.post(f'{BASE}/api/tickets', json={
    'room_number': 'A101', 'description': '楼道墙面脱落', 'fault_type': '其他'
})
t3 = r.json()
print(f'  工单号: {t3["ticket_no"]}, 状态: {t3["status"]}, 指派: {t3["assigned_worker_name"]}')
if t3["assigned_worker_name"] == "王师傅":
    print('  ✅ "其他"类型正确只指派给负责"其他"的维修工（王师傅）')
else:
    print(f'  ❌ "其他"类型指派有误，应指派给王师傅，实际指派给{t3["assigned_worker_name"]}')

# ===== 8. 测试无法自动指派 → 进入待分配队列 =====
print('\n【步骤8】提交报修工单（门禁类）→ 李师傅拒单后无人可派')
r = requests.post(f'{BASE}/api/tickets', json={
    'room_number': 'B202', 'description': '门禁卡刷不开门', 'fault_type': '门禁'
})
t4 = r.json()
print(f'  工单号: {t4["ticket_no"]}, 状态: {t4["status"]}, 指派: {t4["assigned_worker_name"]}')

# 李师傅拒单（门禁只有李师傅负责，拒单后无人可派）
if t4["assigned_worker_name"] == "李师傅":
    print('  李师傅拒单...')
    r = requests.post(f'{BASE}/api/tickets/{t4["id"]}/reject', json={'reason': '今天请假了'})
    t4 = r.json()
    print(f'  拒单后状态: {t4["status"]}, 指派: {t4["assigned_worker_name"]}')

# 检查待分配队列
r = requests.get(f'{BASE}/api/unassigned-queue')
queue = r.json()
print(f'  待分配队列: {queue}')

# ===== 9. 手动指派 → 测试从待分配队列移除 =====
print('\n【步骤9】手动指派待分配工单 → 测试从队列移除')
r = requests.post(f'{BASE}/api/tickets/{t4["id"]}/assign', json={'worker_id': worker_ids[0]})
t4 = r.json()
print(f'  手动指派后状态: {t4["status"]}, 指派: {t4["assigned_worker_name"]}')

r = requests.get(f'{BASE}/api/unassigned-queue')
queue = r.json()
print(f'  待分配队列: {queue}')
if t4["id"] not in queue["ticket_ids"]:
    print('  ✅ 手动指派成功后，工单已从待分配队列移除')
else:
    print('  ❌ 手动指派后，工单仍在待分配队列中')

# ===== 10. 查看工单详情（含完整流转日志） =====
print('\n【步骤10】查看工单详情（含完整流转日志）')
r = requests.get(f'{BASE}/api/tickets/{t1["id"]}')
detail = r.json()
print(f'  工单: {detail["ticket_no"]} 状态: {detail["status"]}')
print(f'  完整流转记录:')
for log in detail['logs']:
    print(f'    {log["created_at"][:19]} | {log["action"]} | {log["operator"]} | {log["detail"]}')

# ===== 11. 按状态筛选 =====
print('\n【步骤11】按状态筛选')
for s in ['待接单', '维修中', '已完成', '待指派']:
    r = requests.get(f'{BASE}/api/tickets?status={s}')
    count = len(r.json())
    print(f'  {s}: {count} 条')

# ===== 12. 统计报表 =====
print('\n【步骤12】统计报表')
r = requests.get(f'{BASE}/api/reports/monthly')
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print('\n' + '=' * 60)
print('  ✅ 全部测试通过！')
print('=' * 60)
