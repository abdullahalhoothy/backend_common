from fastapi import FastAPI, Depends
from backend_common.auth import JWTBearer


app = FastAPI()


@app.get('/index', dependencies=[Depends(JWTBearer())])
def index():
    return {'message': 'Hello World'}
