from datetime import datetime
from datetime import timedelta
import json
from json import JSONEncoder
import qrcode
import os
from datetime import timezone

date_keys = ['created_at', 'start_time', 'end_time', 'last_modified']

def SQL_one_line(sql):
    return ' '.join(sql.replace('\n', ' ').split())

def dict_dates_to_utc(list_of_dict):    
    for d in list_of_dict:        
        for key, value in d.items():
            if key in date_keys:         
                d[key] = d[key].replace(tzinfo=timezone.utc)
               

def make_qr(user_id: int, path) -> None:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=0,
    )
    qr.add_data(str(user_id))
    qr.make(fit=True)

    name = '{}.png'.format(user_id)

    qr.make_image().get_image().save(os.path.join(path, name))


class DateTimeEncoder(JSONEncoder):
    """ Converts datetime to ISO string before being encoded to JSON
    """

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, timedelta):
            return str(obj)
        else:
            return JSONEncoder.default(self, obj)


def encode_json(obj):
    """ Will encode datetime to ISO string for JSON serialisation"""
    return json.dumps(obj, cls=DateTimeEncoder)


def parse_range(a_str):
    result=set()
    for part in a_str.split(','):
        x=part.split('-')
        result.update(range(int(x[0]),int(x[-1])+1))
    return sorted(result)

if __name__ == "__main__":

    print('Testing JSON')

    data = {'name': 'steve', 'dob': datetime.utcnow()}

    print('python dictionary data:', data)

    text = encode_json(data)

    print('JSON: ', text)

    print('Testing page range parser')

    ranges = '1-5, 34', '45, 1', '20-5', '5-20'

    for i in ranges:
        print(i, '->', parse_range(i))

