from ib_insync import IB
ib = IB()
try:
    ib.connect('127.0.0.1', 7497, clientId=99)
    print('Connected successfully!')
    print('Server version:', ib.client.serverVersion())
    ib.disconnect()
except Exception as e:
    print('Connection failed:', e)
