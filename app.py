import os

from flask import request
from flask import make_response
from flask import Flask
from flask import render_template

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


@app.route('/user/<int:id>', methods=['GET', 'DELETE'])
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


@app.route("/user", methods=['POST', 'GET'])
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


@app.route('/user/card/<user_selection>')
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


@app.route('/user/generate_qr/<user_selection>')
def generate_qr(user_selection):

    ids = parse_range(user_selection)

    try:
        for i in ids:
            make_qr(i, QR_CODE_PATH)
    except Exception as e:
        return make_failed_response(str(e))
    else:
        return make_success_response(ids)


if __name__ == "__main__":
    app.run(debug=DEBUG, host='0.0.0.0', port=53455)
