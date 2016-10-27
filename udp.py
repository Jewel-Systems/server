import socket
import threading
from log import log

web_server_port = 53455
listen_port = 53456
reply_port = 53457
debug_timeout = 10  # seconds

d = None

def daemon():
    # find local IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 0))
    local_ip_address = s.getsockname()[0]
    s.close()

    # listen and reply
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # s.settimeout(debug_timeout)
    
    try:
        s.bind(('0.0.0.0', listen_port))
        
    except Exception:
        log.warn('Could not bind 0.0.0.0:{}'.format(listen_port))
    else:
        log.debug('UDP bound')
        while True:    
            try:
                data, addr = s.recvfrom(4096)  # blocks
                print('{ip}:{port}  {data}'.format(data=data.decode('ascii'), ip=addr[0], port=addr[1]))
                reply = str(web_server_port).encode('ascii')        
                s.sendto(reply, (addr[0], reply_port))
                log.debug('Sent a reply to ' + str(addr))
            
            except socket.timeout:
                print('Listening duration elapsed.')
                break

    s.close()

  
def go():
    d = threading.Thread(name='daemon', target=daemon)
    d.setDaemon(True)
    d.start()
