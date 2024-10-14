from fastapi import FastAPI, Depends
from backend_common.auth import JWTBearer


app = FastAPI()


@app.get('/index', dependencies=[Depends(JWTBearer())])
# this needs to use request_handling
def index():
    return {'message': 'Hello World'}




