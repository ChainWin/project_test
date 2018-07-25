# coding: utf-8

from pymongo import MongoClient

cli = MongoClient()
cli.flask.authenticate("Yun", "chenyun1993")
db = cli.flask

# 数据库是否确定用哪一个？


