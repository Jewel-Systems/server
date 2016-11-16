import os

from dateutil.parser import parse as date_parse

from datetime import timezone, datetime

from flask import Flask, request, make_response, render_template, Response, g, jsonify

from flask_cors import CORS, cross_origin

from flask_weasyprint import HTML, render_pdf

from functools import wraps

import mysql.connector
import bcrypt

import config
from util import (encode_json,
                  parse_range,
                  make_qr,
                  dict_dates_to_utc,
                  SQL_one_line)

from log import log

import udp

log.info ('Start.')

DEBUG = False

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

QR_CODE_PATH = os.path.join(APP_ROOT, 'static', 'img', 'qr')

app = Flask(__name__)

CORS(app)

udp.go()


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    
    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(dictionary=True)
   
    # user name may be the user's id or their email
    if username.isdigit():
        cursor.execute(""" SELECT * FROM user
                            WHERE id = %s """, (username,))
        
    else:
        cursor.execute(""" SELECT * FROM user
                            WHERE email = %s """, (username,))

    rows = cursor.fetchall()
    
    g.user = rows[0]
        
    if not len(rows):
        return False
                            
    if bcrypt.checkpw(password.encode('ascii'), rows[0]['password'].encode('ascii')):
        return True
    else:
        return False


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

    
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


def get_database():
    """ returns a connection and cursor

    e.g. cnx, cursor = get_database()
    """

    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(named_tuple=True)

    return cnx, cursor


def make_success_response(data, code=200, mimetype='application/json'):
    payload = encode_json({'success':  True, 'data': data})
    resp = make_response(payload, code)
    resp.mimetype = mimetype
    return resp


def make_failed_response(error_message, code=400, mimetype='application/json', data=None):
    payload = encode_json({'success': False, 'error': error_message, 'data':data})
    resp = make_response(payload, code)
    resp.mimetype = mimetype
    return resp


def test_reservation(start, end, type):
    '''
        find reservations which collide with the given start and end datetime and match type
    '''
    
    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(dictionary=True)
    
    cursor.execute("""
                        SELECT * FROM reservation
                        
                        WHERE  DATE_SUB(start_time, INTERVAL safe_zone hour_second) -- start of current reservations
                        
                        < %s -- end of new reservation 
                          
                        AND end_time -- end of current reservations
                          
                        >= %s -- start of new reservation    
                        
                        AND type = %s
                        
                        ; """, (start, end, type))
    
    colliding_reservations = cursor.fetchall()
    
    log.info('Executed SQL:' + SQL_one_line(cursor.statement))
    # log.info('Colliding reservations ' + str([row['id'] for row in colliding_reservations]))
    cursor.close()
    cnx.close()
    
    return colliding_reservations
    

@app.route('/api/v1/log')
def log_endpoint ():  
    log_lines = []
    
    with open('app.log', 'r') as logfile:
        log_lines = logfile.readlines()
        
    log_lines.sort(key=lambda x:x[:25], reverse=True)
        
    return "".join(log_lines)  
    
    
@app.route('/api/v1/testauth', methods=['POST'])
def testauth():

    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(dictionary=True)
        
    test_user = request.get_json(force=True)
        
    try:
        # user name may be the user's id or their email
        if test_user['username'].isdigit():
            cursor.execute(""" SELECT * FROM user
                                WHERE id = %s """, (test_user['username'],))
            
        else:
            cursor.execute(""" SELECT * FROM user
                                WHERE email = %s """, (test_user['username'],))
              
    except Exception as e:
        return make_failed_response(str(e))
        
    else:
        rows = cursor.fetchall()
        
        # user does not exist
        if not len(rows):
            return make_failed_response("id / email not found")

        else:
            if not config.app['password_needed']:
                rows[0].pop('password')
                return make_success_response(rows[0])            
            
            # test password
            if bcrypt.checkpw(test_user['password'].encode('ascii'), rows[0]['password'].encode('ascii')):
                rows[0].pop('password')
                return make_success_response(rows[0])
            else:
                return make_failed_response('incorrect password')
                
    finally: 
        cursor.close()
        cnx.close()

# -----------------------------------------------------------------------------
# Users
# -----------------------------------------------------------------------------
    
@app.route('/api/v1/user/<int:id>', methods=['GET', 'DELETE'])
def one_user(id):
    # get a user
    if request.method == "GET":
        cnx = mysql.connector.connect(**config.db)
        cursor = cnx.cursor(dictionary=True)
        
        try:
            cursor.execute(""" SELECT id, email, fname, lname, type, created_at
                               FROM user
                               WHERE id = %s """, (id,))
                               
        except Exception as e:
            return make_failed_response(str(e))
            
        else:
            rows = cursor.fetchall()
            
            if not len(rows):
                return make_failed_response("id not found")
                
            else:            
                # get their loaned devices                
                cursor.execute(""" SELECT * FROM device
                                   WHERE loaned_by = %s; """,
                               (id,))
                               
                loaned = cursor.fetchall()
                
                # get their privilages
                cursor.execute(""" SELECT type FROM device_type_privilage
                                   WHERE user_id = %s; """,
                               (id,))
            
                privilages = cursor.fetchall()
            
                rows[0]['loaned'] = loaned
                rows[0]['privilages'] = privilages
            
                return make_success_response(rows[0])
                
        finally:
            cursor.close()
            cnx.close()

    # delete a user
    if request.method == "DELETE":
        cnx = mysql.connector.connect(**config.db)
        cursor = cnx.cursor()
        try:
            cursor.execute(""" DELETE FROM user
                               WHERE id = %s """, (id,))
        except Exception as e:
            return make_failed_response(str(e))
        else:
            cnx.commit()
            if not cursor.rowcount:
                return make_failed_response("id not found")
            else:
                return make_success_response(dict(id=id))
        finally:
            cursor.close()
            cnx.close()


@app.route("/api/v1/user", methods=['POST', 'GET'])
def user():
    
    # add a new user
    if request.method == "POST":
        cnx, cursor = get_database()
        
        new_user = request.get_json(force=True)
        
        hashed_password = bcrypt.hashpw(new_user['password'].encode(), bcrypt.gensalt())
        
        try:            
            cursor.execute(
                """ INSERT INTO user (email, fname, lname, type, password)
                               VALUES (%s, %s, %s, %s, %s); """,
                (
                    new_user["email"],
                    new_user["fname"],
                    new_user["lname"],
                    new_user["type"],
                    hashed_password
                )
            )
                            
        except Exception as e:            
            cnx.rollback()    
            
            msg = str(e)            
            if 'email_UNIQUE' in msg:
                return make_failed_response("Sorry, that email is taken!")
            
            return make_failed_response(msg)
            
        else:
            cnx.commit()
            new_id = cursor.lastrowid
            data = dict(id=new_id)
            make_qr(new_id, QR_CODE_PATH)
            return make_success_response(data)
            
        finally:
            cursor.close()
            cnx.close()

    # get all users
    if request.method == "GET":
        cnx = mysql.connector.connect(**config.db)
        cursor = cnx.cursor(dictionary=True)

        try:
            cursor.execute(""" SELECT id, email, fname, lname, type, created_at 
                               FROM user """)
        except Exception as e:
            return make_failed_response(str(e))
        else:
            return make_success_response(cursor.fetchall())
        finally:
            cursor.close()
            cnx.close()
            
            
@app.route('/api/v1/user/<int:user_id>/privilege/<type>', methods=['PUT', 'DELETE'])
def user_privilage (user_id, type):
    cnx, cursor = get_database()

    if request.method == 'PUT':
        try:
            cursor.execute(""" INSERT INTO device_type_privilage (user_id, type)
                               VALUES (%s, %s); """, (user_id, type))
        except Exception as e:
            log.error('Attempted SQL: ' + SQL_one_line(cursor.statement))
            
            e = 'User {} already has privilage for device type "{}"'.format(user_id, type)
            log.info(e)
            return make_failed_response(e)
        else:
            cnx.commit()
            return make_success_response(dict(id=cursor.lastrowid))
        finally:
            cursor.close()
            cnx.close()
            
    if request.method == 'DELETE':
        try:
            cursor.execute(""" DELETE FROM device_type_privilage
                               WHERE user_id = %s
                               AND type = %s; """, (user_id, type))
        except Exception as e:
            return make_failed_response(str(e))
        else:
            cnx.commit()
            if not cursor.rowcount:
                return make_failed_response("ids not found")
            else:
                log.info('Removed privilege {} for {}'.format(type, user_id))
                return make_success_response(dict(user_id=user_id, type=type))
        finally:
            cursor.close()
            cnx.close()
            
# -----------------------------------------------------------------------------
# Cards
# -----------------------------------------------------------------------------
  
@app.route('/api/v1/user/card/<user_selection>')
def user_card(user_selection):
    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(dictionary=True)

    ids = parse_range(user_selection)

    sql_where = ', '.join(str(i) for i in ids)

    cursor.execute(""" SELECT id, email, fname, lname, type, created_at FROM user
                       WHERE id IN ({});""".format(sql_where))  # yes, this is safe

    data = cursor.fetchall()

    cursor.close()
    cnx.close()

    return render_template('cards.html', users=data)
    

@app.route('/api/v1/user/card/<user_selection>/pdf')
def user_card_pdf(user_selection):
    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(dictionary=True)

    ids = parse_range(user_selection)

    sql_where = ', '.join(str(i) for i in ids)

    cursor.execute(""" SELECT id, email, fname, lname, type, created_at FROM user
                       WHERE id IN ({});""".format(sql_where))  # yes, this is safe

    data = cursor.fetchall()

    cursor.close()
    cnx.close()

    # Make a PDF straight from HTML in a string.
    html = render_template('cards.html', users=data)
    return render_pdf(HTML(string=html))
    
      
@app.route('/api/v1/user/generate_qr/<user_selection>')
def generate_qr(user_selection):

    ids = parse_range(user_selection)

    try:
        for i in ids:
            make_qr(i, QR_CODE_PATH)
    except Exception as e:
        return make_failed_response(str(e))
    else:
        return make_success_response(ids)
        
        
# -----------------------------------------------------------------------------
# Devices
# -----------------------------------------------------------------------------  

@app.route('/api/v1/device', methods=['POST', 'GET'])
def device ():
    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(dictionary=True)
    
    if request.method == 'GET':
        try:
            cursor.execute(""" SELECT * FROM device; """)
        except Exception as e:
            return make_failed_response(str(e))
        else:        
            data = cursor.fetchall()
            for row in data:
                row['is_active'] = True if row['is_active'] else False            
            return make_success_response(data)
        finally:
            cursor.close()
            cnx.close()
    
    # add a new device
    if request.method == "POST":

        cnx, cursor = get_database()
        
        new_device = request.get_json(force=True)
        
        try:
            cursor.execute(
                """ INSERT INTO device (serial_no, type, is_active)
                               VALUES (%s, %s, %s); """,
                (
                    new_device["serial_no"],
                    new_device["type"],
                    new_device.get("is_active", False),
                )
            )
                            
        except Exception as e:
            cnx.rollback()
            return make_failed_response(str(e))
        else:
            cnx.commit()
            new_id = cursor.lastrowid
            make_qr(new_id, QR_CODE_PATH)
            data = dict(id=new_id)
            return make_success_response(data)
        finally:
            cursor.close()
            cnx.close()


@app.route('/api/v1/device/<int:id>', methods=['GET', 'DELETE'])
def one_device(id):
    # get a device
    if request.method == "GET":
        cnx = mysql.connector.connect(**config.db)
        cursor = cnx.cursor(dictionary=True)
        try:
            cursor.execute(""" SELECT * FROM device
                               WHERE id = %s """, (id,))
        except Exception as e:
            return make_failed_response(str(e))
        else:
            rows = cursor.fetchall()
            if not len(rows):
                return make_failed_response("id not found")
            else:
                return make_success_response(rows[0])
        finally:
            cursor.close()
            cnx.close()

    # delete a device
    if request.method == "DELETE":
        cnx = mysql.connector.connect(**config.db)
        cursor = cnx.cursor()
        try:
            cursor.execute(""" DELETE FROM device
                               WHERE id = %s """, (id,))
        except Exception as e:
            return make_failed_response(str(e))
        else:
            cnx.commit()
            if not cursor.rowcount:
                return make_failed_response("id not found")
            else:
                return make_success_response(dict(id=id))
        finally:
            cursor.close()
            cnx.close()


@app.route('/api/v1/device/<int:id>/active', methods=['PUT', 'DELETE'])
def device_active (id):

    cnx, cursor = get_database()

    is_active = True 
    
    if request.method == 'DELETE':
        is_active = False 
    
    cursor.execute(""" UPDATE device SET is_active=%s WHERE id = %s; """,
                    (is_active, id))
            
        
    cnx.commit()
    cursor.close()
    cnx.close()    
    
        
    return ('', 200)

 
@app.route('/api/v1/device/<int:device_id>/loan/<int:user_id>', methods=['PUT', 'DELETE'])
def loan (device_id, user_id):
    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(dictionary=True)
    
    # attempt to loan
    if request.method == 'PUT':        
        # is user privilaged for this device?        
        cursor.execute(""" SELECT COUNT(device_type_privilage.type) AS count
                           FROM device, device_type_privilage
                           WHERE device.type = device_type_privilage.type
                           AND device_type_privilage.user_id = %s
                           AND device.type = (SELECT type FROM device WHERE id = %s);""",
                           (user_id,device_id))
        
        row = cursor.fetchone()
        
        count = row['count']
        
        log.info('[check] [privilage] Executed SQL: ' + SQL_one_line(cursor.statement))
        
        
        
        
        if count == 0:
            log.info('[check] [privilage] User {} not privilaged to loan device {}'.format(user_id, device_id))
            return make_failed_response(error_message = 1)
        
        
        # is the device loaned by a user?
        cursor.execute(""" SELECT COUNT(id) AS count, loaned_by, type
                           FROM device WHERE id = %s
                           AND loaned_by IS NOT NULL """, (device_id,))        
        device = cursor.fetchone()        
        if device['count']:
            log.info('[check] [loan] Device {} already loaned.'.format(device_id))
            cursor.execute(""" SELECT user.id, user.email, user.fname, 
                               user.lname, user.type, user.created_at
                               FROM user
                               WHERE user.id = %s; """, (device['loaned_by'],))                               
            user = cursor.fetchone()            
            return make_failed_response(error_message = 2, data = user)
            
        
        else:            
            # we now check safety
            
            now = datetime.utcnow().replace(tzinfo=timezone.utc)
            
            cursor.execute("""SELECT type FROM device WHERE id = %s""", (device_id,))
            
            device_type = cursor.fetchone()['type']
            
            log.info('[check] [safety] Device type: {}'.format(device_type))           
            
            colliding_reservations = test_reservation(now, now, device_type)
            
            log.info('[check] [safety] Colliding reservations: {}'.format(colliding_reservations))
            
            cursor.execute(""" SELECT COUNT(*) AS count FROM device WHERE type = %s AND is_active = 1""", (device_type,))
            
            total_devices = cursor.fetchone()['count']
            
            total_reserved = sum([int(row['count']) for row in colliding_reservations])
            
            log.info('[check] [safety] total_reserved: ' + str(total_reserved))
            
            log.info('[check] [safety] Total active devices ({}): {}'.format(device_type, total_devices))
            
            remaining = total_devices - total_reserved - 1
            
            log.info ('[check] [safety] Active devices which will be left: ' + str(remaining))
            
            if remaining < 0:
                if len(colliding_reservations) == 0: # there are plainly no active unloaned devices left,
                                                     # even if there are no reservations
                                                     # ideally, this should never happen as an inactive 
                                                     # and unloaned device wouldn't normally be requested
                                                     
                    log.info ('[check] [safety] Failed, remaining = {}'.format(remaining))                          
                    return make_failed_response(error_message=3)
            
                # now only allow if student is in one of the classes of any of the colliding reservations
                cursor.execute(""" SELECT class_id FROM class_registration WHERE user_id = %s """, (user_id,))
            
                user_classes = set([row['class_id'] for row in cursor.fetchall()])
                reservation_classes = set([row['class_id'] for row in colliding_reservations])
                common_classes = user_classes.intersection(reservation_classes)
            
                log.info('[check] [safety] user classes: {}'.format(user_classes))
                log.info('[check] [safety] reservation classes: {}'.format(reservation_classes))
                log.info('[check] [safety] no. of common classes: {}'.format(len(common_classes)))
                
                if len(common_classes) == 0:
                    log.info('[check] [safety] Failed. common classes = 0')
                    return make_failed_response(error_message=3, data = colliding_reservations)
                               
            
            log.info('[check] [safety] All checks passed.')
            cursor.execute(""" UPDATE device SET loaned_by = %s
                               WHERE device.id = %s """, (user_id, device_id))
            cnx.commit()
            cursor.close()
            cnx.close()
            
            return make_success_response (data=dict(device_id=device_id, user_id=user_id))
            
            
        
    # attempt to return device
    if request.method == 'DELETE':
        
        # check same user returning, device  exists, or is loaned
        cursor.execute(""" SELECT COUNT(id) AS count
                           FROM device WHERE id = %s
                           AND loaned_by = %s """, (device_id, user_id))
                           
        count = cursor.fetchone()['count']
        
        if count == 0:
            return make_failed_response (error_message='invalid user/device')

        cursor.execute(""" UPDATE device 
                           SET loaned_by = NULL
                           WHERE device.id = %s; """, (device_id,))
                           
        cnx.commit()
        cursor.close()
        cnx.close()

        return make_success_response (data=dict(device_id=device_id, user_id=user_id))


@app.route('/api/v1/device/type', methods=['GET'])        
def device_type ():
    cnx, cursor = get_database()
    
    cursor.execute(""" SELECT DISTINCT type FROM device; """)
    
    types = [row.type for row in cursor.fetchall()]
    
    cursor.close()
    cnx.close()
    
    log.info(str(types))
    
    return make_success_response(data=types)

@app.route('/api/v1/device/card/<device_selection>/pdf')
def device_cards(device_selection):
    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(dictionary=True)

    ids = parse_range(device_selection)

    sql_where = ', '.join(str(i) for i in ids)

    cursor.execute(""" SELECT id, type, serial_no, type FROM device
                       WHERE id IN ({});""".format(sql_where))

    data = cursor.fetchall()

    cursor.close()
    cnx.close()

    # Make a PDF straight from HTML in a string.
    html = render_template('devices.html', devices=data)
    return render_pdf(HTML(string=html))
    
# -----------------------------------------------------------------------------
# Reservation
# -----------------------------------------------------------------------------  

@app.route('/api/v1/reservation', methods=['GET', 'POST'])
def reservation ():
    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(dictionary=True)
    
    # get all reservations
    if request.method == 'GET':
        try:
            cursor.execute(""" SELECT * FROM reservation; """)
            
        except Exception as e:
            return make_failed_response(str(e))
            
        else:        
            reservations = cursor.fetchall()
            dict_dates_to_utc(reservations)            
            return make_success_response(reservations)
            
        finally:
            cursor.close()
            cnx.close()
        
    # add reservation
    if request.method == 'POST':
        new_reservation = request.get_json(force=True)
        
        start_time = date_parse(new_reservation['start_time']).astimezone(tz=timezone.utc)
        end_time = date_parse(new_reservation['end_time']).astimezone(tz=timezone.utc)
        
        # we now check safety
        colliding_reservations = test_reservation(start_time, end_time, new_reservation['type'])
                
        cursor.execute(""" SELECT COUNT(*) AS count FROM device WHERE type = %s AND is_active = 1""", (new_reservation['type'],))
        
        total_devices = cursor.fetchone()['count']
        
        total_reserved = sum([int(row['count']) for row in colliding_reservations])
        
        log.info('Total reserved: {}'.format(total_reserved))
        
        log.info('Total active Devices ({}): {}'.format(new_reservation['type'], total_devices))
        
        remaining = total_devices - total_reserved - new_reservation['count']
        
        log.info('Devices which may be left: {}'.format(remaining))
        
        # there is likely not going to be enough devices of this type to go 
        # around at some point where the new reservation and current ones collide
        if remaining < 0:
            log.info('Failed. remaining devices will be <= 0')
            return make_failed_response(error_message=1, data = colliding_reservations)
        
        try:
            cursor.execute(
                """ INSERT INTO reservation (start_time,
                                             end_time,
                                             class_id,
                                             type,
                                             count,
                                             user_id,
                                             safe_zone)
                               VALUES (%s, %s, %s, %s, %s, %s, %s); """,
                (
                    start_time,
                    end_time,
                    new_reservation['class_id'],
                    new_reservation['type'],
                    new_reservation['count'],
                    new_reservation['user_id'],
                    new_reservation.get('safe_zone', '01:00:00')
                )
            )
                            
        except Exception as e:
            cnx.rollback()
            return make_failed_response(str(e))
        else:
            log.info('Add success.')
        
            cnx.commit()
            new_id = cursor.lastrowid
            data = dict(id=new_id)
            return make_success_response(data)
        finally:
            cursor.close()
            cnx.close()

@app.route('/api/v1/reservation/<int:id>', methods=['DELETE', 'GET'])
def one_reservation(id):
    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(dictionary=True)

    # delete (revoke) a reservation
    if request.method == 'DELETE':
        try:
            cursor.execute(""" DELETE FROM reservation
                               WHERE id = %s """, (id,))
                               
        except Exception as e:
            return make_failed_response(str(e))
            
        else:
            cnx.commit()
            if not cursor.rowcount:
                return make_failed_response("id not found")
            else:
                return make_success_response(dict(id=id))
                
        finally:
            cursor.close()
            cnx.close()
        
    if request.method == 'GET':
        try:
            cursor.execute(""" SELECT * FROM reservation
                               WHERE id = %s """, (id,))
                               
        except Exception as e:
            return make_failed_response(str(e))
            
        else:
            rows = cursor.fetchall()
            if not len(rows):
                return make_failed_response("id not found")
                
            else:
                dict_dates_to_utc(rows)
                return make_success_response(rows[0])
                
        finally:
            cursor.close()
            cnx.close()

# -----------------------------------------------------------------------------
# Classes (Academic)
# -----------------------------------------------------------------------------  
    
@app.route('/api/v1/class', methods=['GET', 'POST'])
def all_class ():
    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(dictionary=True)
    
    # get all classes
    if request.method == 'GET':
        try:
            cursor.execute(""" SELECT * FROM class; """)
            
        except Exception as e:
            return make_failed_response(str(e))
            
        else:        
            data = cursor.fetchall()           
            return make_success_response(data)
            
        finally:
            cursor.close()
            cnx.close()
    
    # add a new class
    if request.method == "POST":

        cnx, cursor = get_database()
        
        new_class = request.get_json(force=True)
        
        try:
            cursor.execute(
                """ INSERT INTO class (name)
                               VALUES (%s); """,
                (
                    new_class["name"],
                )
            )
                            
        except Exception as e:
            log.error('Attempted SQL: ' + SQL_one_line(cursor.statement))
            cnx.rollback()
            return make_failed_response(str(e))
            
        else:
            cnx.commit()
            new_id = cursor.lastrowid
            data = dict(id=new_id)
            return make_success_response(data)
            
        finally:
            cursor.close()
            cnx.close()
            
            
@app.route('/api/v1/class/<int:id>', methods=['GET', 'DELETE'])
def one_class (id):
    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(dictionary=True)
    
    # get a class
    if request.method == "GET":
        try:
            cursor.execute(""" SELECT * FROM class
                               WHERE `class`.`id` = %s """, (id,))
                               
            classes = cursor.fetchall()
                               
            
        except Exception as e:
            return make_failed_response(str(e))
        else:
            if not len(classes):
                return make_failed_response("id not found")
            else:
                # now we get who is registered for this class                
                cursor.execute(""" SELECT user.id, user.email, user.fname, 
                                   user.lname, user.type, user.created_at
                                   FROM class_registration, user
                                   WHERE class_registration.class_id = %s 
                                   AND class_registration.user_id = user.id;""", (id,))
                
                users = cursor.fetchall()                
                
                classes[0]['users'] = users
                
                log.info (str(classes))
            
                return make_success_response(classes[0])
        finally:
            cursor.close()
            cnx.close()
    
    # remove a class
    if request.method == "DELETE":
        
        cnx, cursor = get_database()
        
        try:
            cursor.execute(""" DELETE FROM class
                               WHERE id = %s """, (id,))
        except Exception as e:
            msg = 'Failed to delete class {}. There may still be a user part of it.'.format(id, str(e))
            log.info(msg)
            return make_failed_response(msg)
        else:
            cnx.commit()
            if not cursor.rowcount:
                return make_failed_response("id not found")
            else:
                log.info('Deleted class {}.'.format(id))
                return make_success_response(dict(id=id))
        finally:
            cursor.close()
            cnx.close()


@app.route('/api/v1/class/<int:class_id>/user/<int:user_id>', methods=['PUT', 'DELETE'])
def class_register (class_id, user_id):
    cnx, cursor = get_database()

    # register user
    if request.method == 'PUT':
        try:
            cursor.execute(""" INSERT INTO class_registration (class_id, user_id)
                               VALUES (%s, %s); """, (class_id,user_id))
        except Exception as e:
            return make_failed_response(str(e))
        else:
            cnx.commit()
            return make_success_response(dict(id=cursor.lastrowid))
        finally:
            cursor.close()
            cnx.close()

    # deregister user
    if request.method == 'DELETE':
        try:
            cursor.execute(""" DELETE FROM class_registration
                               WHERE class_id = %s
                               AND user_id = %s; """, (class_id,user_id))
        except Exception as e:
            return make_failed_response(str(e))
        else:
            cnx.commit()
            if not cursor.rowcount:
                return make_failed_response("ids not found")
            else:
                return make_success_response(dict(class_id=class_id, user_id=user_id))
        finally:
            cursor.close()
            cnx.close()
            
    
@app.route('/api/v1/lateness', methods=['GET', 'POST'])
def lateness():
    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(dictionary=True)
    
    if request.method == 'POST':
        new_lateness = request.get_json(force=True)
        
        d = date_parse(new_lateness['datetime'])
        
        try:
            d = d.astimezone(tz=timezone.utc)
        except ValueError:
            return make_failed_response(str(e))
        
        
        log.info(str(d))
        
        try:
            cursor.execute(""" INSERT INTO lateness (user_id, datetime) 
                               VALUES (%s, %s) """,
                               (new_lateness['user_id'],
                                d))
               
        except Exception as e:
            cnx.rollback()
            return make_failed_response(str(e))
            
        else:
            cnx.commit()
            new_id = cursor.lastrowid
            data = dict(id=new_id)
            return make_success_response(data)
            
        finally:
            cursor.close()
            cnx.close()
            
            
    if request.method == 'GET':
        
        cursor.execute (""" SELECT * FROM lateness; """)
        
        rows = cursor.fetchall()
        
        dict_dates_to_utc(rows)

        cursor.close()
        cnx.close()
        
        return make_success_response(data = rows)

        
# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------  
@app.route('/api/v1/config')
def app_config():
    return jsonify (config.app)
      
      
if __name__ == "__main__":
    DEBUG = True
    app.run(debug=DEBUG, host='0.0.0.0', port=53455)
