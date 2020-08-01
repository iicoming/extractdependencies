# -*- encoding: utf-8 -*-
"""
@File    : config.py
@Time    : 2020/08/01 10:08
@Author  : iicoming@hotmail.com
"""
config = {
    'FLAG': True,
    'domain': '',
    'domain_test': '',
    'zip_path_test': '',
    'zip_path': '',
    'host': "",
    'host_test': "127.0.0.1"

}

headers = {
    "Content-Type": "application/json",
    "Host": "{domain}".format(
        domain=config['domain'] if config['FLAG'] else config['domain_test']),
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko)",
    "Cookie":""
}

REDIS_CONFIG = {
    "host": "{host}".format(
        host=config['host'] if config['FLAG'] else config['host_test']),
    "port": 6379,
    "db": 0,
    "password": "",
    "max_connections": 100,
    "socket_timeout": 5,
    "decode_responses": True}
