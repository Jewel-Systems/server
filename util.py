from datetime import datetime
import json
from json import JSONEncoder


class DateTimeEncoder(JSONEncoder):
    """ Converts datetime to ISO string before being encoded to JSON
    """

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
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

