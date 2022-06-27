from flask import Flask, render_template, request, redirect, send_from_directory
from personal_project.config.mysql_config import *
from dotenv import load_dotenv
import os
import datetime
import time
import json
from pprint import pprint

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('secret_key')
app.config['JSON_AS_ASCII'] = False
DEBUG, PORT, HOST = True, 8080, '0.0.0.0'


@app.route('/')
def main():
    return render_template('index.html')


@app.route('/hotels')
def hotels():
    MyDb.ping(reconnect=True)
    cursor = MyDb.cursor()
    dest = request.args.get("dest")
    checkin = request.args.get("checkin")
    checkout = request.args.get("checkout")
    person = request.args.get("person")
    page = request.args.get("page")

    cursor.execute(f"SELECT count(*) AS count FROM hotels WHERE address LIKE '%{dest}%'")
    count = cursor.fetchone()['count']
    MyDb.commit()
    msg = f'為您搜出 {count} 間旅館'
    user_send = {
        'dest': dest,
        'checkin': checkin,
        'checkout': checkout,
        'person': person
    }
    if page is None:
        page = 1
    if count and checkout >= checkin and dest and person:
        cursor.execute(f"SELECT * FROM hotels WHERE address like '%{dest}%' ORDER BY id LIMIT {(int(page)-1)*15},15")
        hotel_data = cursor.fetchall()
        MyDb.commit()
        hid = [x['id'] for x in hotel_data]
        cursor.execute(f'select hotel_id, image from images where hotel_id in {tuple(hid)}')
        image_data = cursor.fetchall()
        MyDb.commit()
        image_dt = {}
        for img in image_data:
            try:
                image_dt[img['hotel_id']].append(img['image'])
            except KeyError:
                image_dt[img['hotel_id']] = []
                image_dt[img['hotel_id']].append(img['image'])
        # image_data = {
        #     x['hotel_id']: x['image']
        #     for x in image_data
        # }
        checkout = datetime.datetime.strptime(checkout, "%Y-%m-%d")
        checkout = (checkout - datetime.timedelta(days=1)).date().isoformat()
        if int(person) < 5:
            person_sql = f'between {person} and {int(person) + 1}'
        elif 5 <= int(person) <= 7:
            person_sql = 'between 5 and 7'
        elif 7 < int(person) <= 10:
            person_sql = 'between 7 and 10'
        else:
            person_sql = f'>={person}'
        cursor.execute(
            f"""
            SELECT re.id, re.hotel_id, re.resource, p.price, re.url
            FROM resources as re 
            inner join price as p on re.id = p.resource_id
            where p.date between '{checkin}' and '{checkout}' and re.hotel_id in {tuple(hid)} and p.person {person_sql} 
            order by hotel_id 
            """
        )
        price = cursor.fetchall()
        price_sum = {}
        for p in price:
            try:
                price_sum[p['id']]['price'] += p['price']
                price_sum[p['id']]['count'] += 1
            except KeyError:
                price_sum[p['id']] = p
                price_sum[p['id']]['count'] = 1
        price_dt = {}
        for p in price_sum.values():
            try:
                price_dt[p['hotel_id']][p['resource']] = (format(int(p['price']/p['count']), ','), p['url'])
            except KeyError:
                price_dt[p['hotel_id']] = {}
                price_dt[p['hotel_id']][p['resource']] = (format(int(p['price']/p['count']), ','), p['url'])
    else:
        hotel_data = ''
        image_dt = ''
        price_dt = ''
        if dest == '':
            msg = "請您輸入想去的地點"
        elif checkin == '':
            msg = "請您輸入入住日期"
        elif checkout == '':
            msg = "請您輸入退房日期"
        elif checkout < checkin:
            msg = "請您輸入有效日期"
        elif person == '':
            msg = "請您輸入人數"
        else:
            msg = f"抱歉找不到 '{dest}'"
    pprint(image_dt)
    return render_template('hotel.html',
                           hotel_data=hotel_data,
                           image_data=image_dt,
                           price=price_dt,
                           msg=msg,
                           user_send=user_send,
                           page=page)


if __name__ == '__main__':
    app.run(debug=DEBUG, host=HOST, port=PORT)