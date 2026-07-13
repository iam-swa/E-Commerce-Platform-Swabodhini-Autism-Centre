import requests

# 1. Login as admin
resp = requests.post('http://127.0.0.1:5000/api/auth/login', json={'phone': '7358665496', 'password': 'admin123'})
print("Login status:", resp.status_code)
data = resp.json()
print("Login data:", data)
token = data.get('token')

# 2. Try to get orders
headers = {'Authorization': f'Bearer {token}'}
resp = requests.get('http://127.0.0.1:5000/api/orders', headers=headers)
print("Orders status:", resp.status_code)
orders = resp.json()
print("Orders:", orders)

# 3. If there is an order, try to update status
if orders:
    order_id = orders[0]['_id']
    print("Updating order:", order_id)
    resp = requests.put(f'http://127.0.0.1:5000/api/orders/{order_id}/status', json={'status': 'Approved'}, headers=headers)
    print("Update status:", resp.status_code)
    print("Update data:", resp.json())
