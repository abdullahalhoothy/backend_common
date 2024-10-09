from fastapi import FastAPI, Depends
from auth import JWTBearer


app = FastAPI()


@app.get('/index', dependencies=[Depends(JWTBearer())])
def index():
    return {'message': 'Hello World'}
