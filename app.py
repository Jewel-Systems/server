import os

from flask import request
from flask import make_response
from flask import Flask
from flask import render_template

from flask_cors import CORS, cross_origin

import mysql.connector
import bcrypt

import config
from util import encode_json
from util import parse_range
from util import make_qr

DEBUG = True

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

QR_CODE_PATH = os.path.join(APP_ROOT, 'static', 'img', 'qr')

app = Flask(__name__)

CORS(app)


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


def make_failed_response(error_message, code=400, mimetype='application/json'):
    payload = encode_json({'success': False, 'error': error_message})
    resp = make_response(payload, code)
    resp.mimetype = mimetype
    return resp

    
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
            # test password
            if bcrypt.checkpw(test_user['password'].encode('ascii'), rows[0]['password'].encode('ascii')):
                rows[0].pop('password')
                return make_success_response(rows[0])
            else:
                return make_failed_response('incorrect password')
            
    finally: 
        cursor.close()
        cnx.close()

    
@app.route('/api/v1/user/<int:id>', methods=['GET', 'DELETE'])
def one_user(id):
    # get a user
    if request.method == "GET":
        cnx = mysql.connector.connect(**config.db)
        cursor = cnx.cursor(dictionary=True)
        try:
            cursor.execute(""" SELECT id, email, fname, lname, type, created_at FROM user
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
            print('User INSERT')
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
            return make_failed_response(str(e))
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
            cursor.execute(""" SELECT id, email, fname, lname, type, created_at FROM user """)
        except Exception as e:
            return make_failed_response(str(e))
        else:
            return make_success_response(cursor.fetchall())
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
            data = dict(id=new_id)
            return make_success_response(data)
        finally:
            cursor.close()
            cnx.close()

            
  
          
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
    

if __name__ == "__main__":
    app.run(debug=DEBUG, host='0.0.0.0', port=53455)
