# coding: utf-8

from pymongo import MongoClient

cli = MongoClient()
cli.adimn.authenticate("Yun", "chenyun1993")
db = cli.adimn

# 数据库是否确定用哪一个？

db.pro_collection.create_index([('project_name', 1)], unique=True)
