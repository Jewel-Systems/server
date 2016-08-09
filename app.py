from flask import request
from flask import make_response
from flask import Flask

import mysql.connector

import bcrypt

import config
from util import encode_json

DEBUG = True

app = Flask(__name__)


def get_database():
    """ returns a connection and cursor

    e.g. cnx, cursor = get_database()
    """

    cnx = mysql.connector.connect(**config.db)
    cursor = cnx.cursor(named_tuple=True)

    return cnx, cursor


def make_success_response(data, code=200):
    payload = encode_json({'success':  True, 'data': data})
    resp = make_response(payload, code)
    return resp


def make_failed_response(error_message, code=400):
    payload = encode_json({'success': False, 'error': error_message})
    resp = make_response(payload, code)
    return resp


@app.route("/user", methods=['POST'])
def user():
    
    # add a new user
    if request.method == "POST":

        cnx, cursor = get_database()
        
        new_user = request.get_json()
        
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
            data = dict(id=cursor.lastrowid)
            return make_success_response(data)
        finally:
            cursor.close()
            cnx.close()


if __name__ == "__main__":
    app.run(debug=DEBUG)
