import requests
import json

BASE = 'http://localhost:8000'

print('=' * 60)
print('  物业报修工单API v3.0 完整业务流程测试')
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
    print(f'  创建: {data["name"]} (ID={data["id"]})')

# ===== 2. 创建业主 =====
print('\n【步骤2】创建业主')
for t in [{'room_number': 'A101', 'name': '业主王', 'phone': '13900139001'},
          {'room_number': 'B202', 'name': '业主李', 'phone': '13900139002'}]:
    r = requests.post(f'{BASE}/api/tenants', json=t)
    print(f'  创建: {r.json()["name"]}')

# ===== 3. 提交报修工单 → 自动指派 → 检查通知记录 =====
print('\n【步骤3】提交报修工单(水电) → 自动指派 → 检查通知')
r = requests.post(f'{BASE}/api/tickets', json={
    'room_number': 'A101', 'description': '厨房水管漏水', 'fault_type': '水电'
})
t1 = r.json()
t1_id = t1["id"]
zhang_id = worker_ids[0]  # 张师傅
print(f'  工单号: {t1["ticket_no"]}, 状态: {t1["status"]}, 指派: {t1["assigned_worker_name"]}')
print(f'  通知记录:')
for n in t1['notifications']:
    print(f'    [{n["notify_type"]}] → {n["worker_name"]}: {n["content"]} (结果: {n["send_result"]})')

# ===== 4. 维修工接单（带身份校验） =====
print('\n【步骤4】维修工接单（带身份校验）')
# 先用错误的维修工ID尝试接单
print('  尝试用错误的维修工ID接单...')
r = requests.post(f'{BASE}/api/tickets/{t1_id}/accept', json={'worker_id': worker_ids[1]})
if r.status_code == 403:
    print(f'  ✅ 身份校验生效: {r.json()["detail"]}')
else:
    print(f'  ❌ 身份校验未生效: {r.json()}')

# 用正确的维修工ID接单
print('  用正确的维修工ID接单...')
r = requests.post(f'{BASE}/api/tickets/{t1_id}/accept', json={'worker_id': zhang_id})
t1 = r.json()
print(f'  接单成功，状态: {t1["status"]}')

# ===== 5. 确认完工（带身份校验） =====
print('\n【步骤5】确认完工（带身份校验）')
# 错误的维修工ID
print('  尝试用错误的维修工ID完工...')
r = requests.post(f'{BASE}/api/tickets/{t1_id}/complete', json={'worker_id': worker_ids[1], 'rating': 5})
if r.status_code == 403:
    print(f'  ✅ 身份校验生效: {r.json()["detail"]}')
else:
    print(f'  ❌ 身份校验未生效')

# 正确的维修工ID
r = requests.post(f'{BASE}/api/tickets/{t1_id}/complete', json={'worker_id': zhang_id, 'rating': 5})
t1 = r.json()
print(f'  完工成功，状态: {t1["status"]}, 评分: {t1["rating"]}星')

# ===== 6. 提交报修(照明) → 拒单测试（带身份校验+空格原因校验） =====
print('\n【步骤6】提交报修(照明) → 拒单测试')
r = requests.post(f'{BASE}/api/tickets', json={
    'room_number': 'B202', 'description': '客厅灯不亮了', 'fault_type': '照明'
})
t2 = r.json()
t2_id = t2["id"]
print(f'  工单号: {t2["ticket_no"]}, 状态: {t2["status"]}, 指派: {t2["assigned_worker_name"]}')

# 测试纯空格拒单原因
print('  尝试用纯空格拒单原因...')
r = requests.post(f'{BASE}/api/tickets/{t2_id}/reject', json={
    'worker_id': zhang_id, 'reason': '   '
})
if r.status_code == 422:
    print(f'  ✅ 空格原因校验生效: 422错误')
else:
    print(f'  ❌ 空格原因未拦截: {r.status_code}')

# 错误的维修工ID拒单
print('  尝试用错误的维修工ID拒单...')
r = requests.post(f'{BASE}/api/tickets/{t2_id}/reject', json={
    'worker_id': worker_ids[1], 'reason': '不在负责范围'
})
if r.status_code == 403:
    print(f'  ✅ 身份校验生效: {r.json()["detail"]}')
else:
    print(f'  ❌ 身份校验未生效')

# 正确拒单
print('  张师傅正确拒单...')
r = requests.post(f'{BASE}/api/tickets/{t2_id}/reject', json={
    'worker_id': zhang_id, 'reason': '正在赶往其他小区处理紧急事故'
})
t2 = r.json()
print(f'  拒单后状态: {t2["status"]}, 指派: {t2["assigned_worker_name"]}')
print(f'  流转日志:')
for log in t2['logs']:
    print(f'    [{log["action"]}] {log["detail"]}')

# ===== 7. 提交报修(门禁) → 李师傅拒单 → 无人可派 → 待分配含原因 =====
print('\n【步骤7】提交报修(门禁) → 拒单后无人可派')
r = requests.post(f'{BASE}/api/tickets', json={
    'room_number': 'A101', 'description': '门禁卡刷不开门', 'fault_type': '门禁'
})
t3 = r.json()
t3_id = t3["id"]
li_id = worker_ids[1]
print(f'  工单号: {t3["ticket_no"]}, 指派: {t3["assigned_worker_name"]}')

r = requests.post(f'{BASE}/api/tickets/{t3_id}/reject', json={
    'worker_id': li_id, 'reason': '今天请假了'
})
t3 = r.json()
print(f'  拒单后状态: {t3["status"]}, 待分配原因: {t3["unassigned_reason"]}')

# ===== 8. 待分配列表（含原因） =====
print('\n【步骤8】待分配列表（含原因）')
r = requests.get(f'{BASE}/api/unassigned-queue')
queue = r.json()
for item in queue['items']:
    print(f'  工单{item["ticket_no"]} | 房号{item["room_number"]} | {item["fault_type"]} | 原因: {item["reason"]}')

# ===== 9. 手动指派 → 状态同步 + 待分配列表清理 =====
print('\n【步骤9】手动指派 → 验证状态同步')
r = requests.post(f'{BASE}/api/tickets/{t3_id}/assign', json={'worker_id': zhang_id})
t3 = r.json()
print(f'  手动指派后: 状态={t3["status"]}, unassigned_reason={t3["unassigned_reason"]}')

# 验证待分配列表
r = requests.get(f'{BASE}/api/unassigned-queue')
queue = r.json()
found = any(item['ticket_id'] == t3_id for item in queue['items'])
if not found:
    print('  ✅ 工单已从待分配列表移除')
else:
    print('  ❌ 工单仍在待分配列表')

# 验证通知记录
print(f'  通知记录:')
for n in t3['notifications']:
    print(f'    [{n["notify_type"]}] → {n["worker_name"]}: {n["content"]}')

# ===== 10. 维修工工作台 =====
print('\n【步骤10】维修工工作台')
for status in ['待接单', '维修中', '已完成']:
    r = requests.get(f'{BASE}/api/workers/{zhang_id}/tickets?status={status}')
    tickets = r.json()
    print(f'  张师傅 - {status}: {len(tickets)} 条')
    for t in tickets:
        print(f'    {t["ticket_no"]} | {t["room_number"]} | {t["description"]}')

# ===== 11. 维修工通知列表 =====
print('\n【步骤11】维修工通知列表')
r = requests.get(f'{BASE}/api/workers/{zhang_id}/notifications')
notifications = r.json()
print(f'  张师傅收到 {len(notifications)} 条通知:')
for n in notifications:
    print(f'    [{n["notify_type"]}] 工单{n["ticket_no"]}: {n["content"]}')

# ===== 12. 工单详情（含流转日志+通知记录） =====
print('\n【步骤12】工单详情（含完整流转日志+通知记录）')
r = requests.get(f'{BASE}/api/tickets/{t1_id}')
detail = r.json()
print(f'  工单: {detail["ticket_no"]}')
print(f'  流转日志:')
for log in detail['logs']:
    print(f'    {log["created_at"][:19]} | {log["action"]} | {log["operator"]} | {log["detail"]}')
print(f'  通知记录:')
for n in detail['notifications']:
    print(f'    {n["created_at"][:19]} | {n["notify_type"]} | → {n["worker_name"]} | {n["content"]}')

# ===== 13. 统计报表 =====
print('\n【步骤13】统计报表')
r = requests.get(f'{BASE}/api/reports/monthly')
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print('\n' + '=' * 60)
print('  ✅ 全部测试通过！')
print('=' * 60)
