import socket
import sys
 

web_server_port = 53455
listen_port = 53456
reply_port = 53457
debug_timeout = 10 # seconds


# find local IP
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(('8.8.8.8', 0))
local_ip_address = s.getsockname()[0]
s.close()

# listen and reply
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(debug_timeout)
s.bind((' ', listen_port))

while True:    
    try:
        data,addr = s.recvfrom(4096) # blocks
        print ('{ip}:{port}  {data}'.format(data=data.decode('ascii'), ip=addr[0], port=addr[1]))        
        reply = str(web_server_port).encode('ascii')        
        s.sendto(reply, (addr[0], reply_port))
    
    except socket.timeout:
        print ('Listening duration elapsed.')
        break

s.close()

