# Authentication

Any endpoints that require auth expect HTTP Basic auth headers.

## Signing in

HTTP POST `/auth`

```JSON

{
    "email_address" : "bob@cedar.com",
    "password" : "WAZZZZZAP"
}
```

### Response

Credentials                     | Response
--------------------------------|----------------------
Correct                         | HTTP 200 OK
Incorrect                       | HTTP 401 Unauthorised
Correct but wrong user type     | HTTP 403 Forbidden

Link-server will store credentials when response is HTTP 200 OK and place them in HTTP Basic Auth headers for every request after.

## Signing out

HTTP GET `/clearauth`

This will clear credentials from link-server.

# Resource Endpoints

We are making attribute "id" "internal_id" as we do not know how client handles uniqueness of users. We may need to add an attribute of uniqueness.

## Add User

HTTP POST `/user`

```JSON

{
    "name" : "Bob Henderson",
    "email_address" : "bob@cedar.com",
    "type" : "teacher"
}
```

### Response:

HTTP 400 OK

```JSON

{
    "internal_id" : 1
}
```

## Get Users

HTTP GET `/user`

### Response:

HTTP 400 OK

```JSON
[
    {
        "internal_id" : 1,
        "name" : "Bob Henderson",
        "email_address" : "bob@cedar.com",
        "type" : "teacher"
    },
    { 
        "..."
    }
]
```

## Get User

HTTP GET `/user/<internal_id>`

### Response:

HTTP 400 OK

```JSON
{
    "internal_id" : 1,
    "name" : "Bob Henderson",
    "email_address" : "bob@cedar.com",
    "type" : "teacher"
}
```



## Get User Cards

HTTP GET `/user/card/<range_internal_id>`

Example: `/user/card/1-5,23`

### Response:

HTTP 400 OK, application/pdf
