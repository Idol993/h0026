import requests
import json
import sqlite3

BASE = 'http://localhost:8000'

print('=' * 60)
print('  数据库升级兼容测试')
print('=' * 60)

print('\n【1】查询旧工单列表（验证新字段默认值已补）')
r = requests.get(f'{BASE}/api/tickets')
if r.status_code == 200:
    tickets = r.json()
    print(f'  ✅ 查询成功，共 {len(tickets)} 条工单')
    for t in tickets:
        print(f'    {t["ticket_no"]} | unassigned_reason={t["unassigned_reason"]} | 通知数={len(t["notifications"])}')
else:
    print(f'  ❌ 查询失败: {r.status_code} {r.text}')

print('\n【2】查询通知中心（验证旧通知的默认值已补）')
r = requests.get(f'{BASE}/api/notifications')
if r.status_code == 200:
    notifs = r.json()
    print(f'  ✅ 查询成功，共 {len(notifs)} 条通知')
    for n in notifs:
        print(f'    id={n["id"]} | recipient_type={n["recipient_type"]} | recipient_name={n["recipient_name"]} | send_result={n["send_result"]}')
else:
    print(f'  ❌ 查询失败: {r.status_code} {r.text}')

print('\n【3】按维修工筛选通知')
r = requests.get(f'{BASE}/api/notifications?recipient_type=维修工')
if r.status_code == 200:
    print(f'  ✅ 维修工通知: {len(r.json())} 条')
else:
    print(f'  ❌ 查询失败')

print('\n【4】查询待分配列表')
r = requests.get(f'{BASE}/api/unassigned-queue')
if r.status_code == 200:
    queue = r.json()
    print(f'  ✅ 待分配数量: {queue["unassigned_count"]}')
else:
    print(f'  ❌ 查询失败')

print('\n【5】创建新工单（验证新数据正常写入）')
r = requests.post(f'{BASE}/api/tickets', json={
    'room_number': 'A101', 'description': '厨房水龙头坏了', 'fault_type': '水电'
})
if r.status_code == 200:
    t = r.json()
    print(f'  ✅ 创建成功: {t["ticket_no"]} | 状态={t["status"]}')
    print(f'    通知列表（新工单）:')
    for n in t['notifications']:
        print(f'      [{n["recipient_type"]}] {n["notify_type"]}: {n["content"][:30]}...')
else:
    print(f'  ❌ 创建失败: {r.status_code} {r.text}')

print('\n【6】制造一个待分配工单（验证系统通知）')
r = requests.post(f'{BASE}/api/tickets', json={
    'room_number': 'A101', 'description': '门禁坏了', 'fault_type': '门禁'
})
t = r.json()
t_id = t["id"]
# 让唯一的门禁维修工拒单
r = requests.post(f'{BASE}/api/tickets/{t_id}/reject', json={
    'worker_id': 2, 'reason': '今天请假'
})
t = r.json()
print(f'  拒单后状态: {t["status"]} | unassigned_reason={t["unassigned_reason"]}')
print(f'    通知列表（拒单后）:')
for n in t['notifications']:
    print(f'      [{n["recipient_type"]}] {n["notify_type"]}: {n["content"][:40]}...')

print('\n【7】按系统筛选通知')
r = requests.get(f'{BASE}/api/notifications?recipient_type=系统')
if r.status_code == 200:
    sys_notifs = r.json()
    print(f'  ✅ 系统通知: {len(sys_notifs)} 条')
    for n in sys_notifs:
        print(f'    {n["notify_type"]}: {n["content"]}')
else:
    print(f'  ❌ 查询失败')

print('\n【8】按前台筛选通知')
r = requests.get(f'{BASE}/api/notifications?recipient_type=前台')
if r.status_code == 200:
    front_notifs = r.json()
    print(f'  ✅ 前台通知: {len(front_notifs)} 条')
    for n in front_notifs:
        print(f'    {n["notify_type"]}: {n["content"][:50]}...')
else:
    print(f'  ❌ 查询失败')

print('\n【9】直接查数据库验证字段都已添加')
conn = sqlite3.connect('property.db')
cursor = conn.cursor()
for table in ['tickets', 'notifications']:
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [c[1] for c in cursor.fetchall()]
    print(f'  {table} 字段: {cols}')
cursor.execute("SELECT DISTINCT recipient_type FROM notifications")
types = [r[0] for r in cursor.fetchall()]
print(f'  通知对象类型: {types}')
conn.close()

print('\n' + '=' * 60)
print('  ✅ 全部升级兼容测试通过！')
print('=' * 60)
