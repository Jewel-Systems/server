import logging
from logging import handlers
PATH = 'app.log'

logging.basicConfig(level=logging.DEBUG)

formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(filename)s] [%(funcName)s] %(message)s')

log = logging.getLogger(__name__)

handler = handlers.RotatingFileHandler(PATH,
                                              maxBytes=500000, # 500kb
                                              backupCount=10)
                                              
handler.setLevel(level=logging.DEBUG)

handler.setFormatter(formatter)
                              
log.addHandler(handler)
