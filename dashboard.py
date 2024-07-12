from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from dbManager import JsonDB, Query
from worker import logging


dashboard = APIRouter()

templates = Jinja2Templates(directory='templates')

@dashboard.get('/dashboard', response_class=HTMLResponse, tags=['Demo Page'])
async def show_dashboard(request: Request):
    model = JsonDB()
    records = model.db.all()
    logging.info(f'{records}')
    return templates.TemplateResponse(
        request=request,
        name='dashboard.html',
        context={'chargers': records}
    )