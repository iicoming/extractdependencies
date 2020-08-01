# -*- encoding: utf-8 -*-
"""
@File    : Dependencies.py
@Time    : 2020/08/01 10:08
@Author  : iicoming@hotmail.com
"""
import json
import os
import tarfile
import xml.etree.cElementTree as ET
import time
import requests
import datetime
import sys
import redis
import shutil
from config.config import config, headers, REDIS_CONFIG

class Dependencies:

    def __init__(self):
        self.today = time.strftime("%Y-%m-%d", time.localtime())
        self.yesterday = (
            datetime.datetime.now() -
            datetime.timedelta(
                days=1)).strftime('%Y-%m-%d')
        self.root_path = config['zip_path'] if config['FLAG'] else config['zip_path_test']
        self.url = 'https://{domain}/api/'.format(
            domain=config['domain'] if config['FLAG'] else config['domain_test'])
        self.client = redis.StrictRedis(**REDIS_CONFIG)

    def catch_exception(func):
        time_now = time.strftime("%Y-%m-%d", time.localtime())

        def wrapper(*args, **kwargs):
            try:
                res = func(*args, **kwargs)
                return res
            except Exception as e:
                print(time_now +
                      ': Error method: \n\t%s,\nException info:\n\t%s' %
                      (func.__name__, e))
                sys.exit()

        return wrapper

    def get_git_info(self, path):
        project_pom = {}
        project_git = {}
        with open(path, "r") as f:
            for line in f.readlines():
                split_line = line.rstrip("\n").split("\t")
                project = split_line[0]
                gitaddress = split_line[1]
                branch = split_line[2]
                pom = split_line[3]
                project_pom[project] = pom
                project_git[project] = gitaddress + "__" + branch
        return (project_git, project_pom)

    def del_yesterday_datas(self,root):
        yesterday_file = root + os.sep + self.yesterday + '.tar.gz'
        yesterday_dir=root + os.sep + self.yesterday
        try:
            shutil.rmtree(yesterday_dir)
        except Exception:
            pass
        try:
            os.remove(yesterday_file)
        except Exception:
            pass


    def is_zip_file_exist(self, root):
        flag = True
        realpath = root + os.sep + self.today + '.tar.gz'
        if not os.path.exists(realpath):
            return False
        self.del_yesterday_datas(root)
        if os.path.exists(root + os.sep + self.today):
            return True
        try:
            tarfile.open(realpath).extractall(path=root)
        except Exception:
            flag = False
        return flag

    def get_parent(self, child):
        for sub_child in child:
            if "groupId" in sub_child.tag:
                parent_groupId = sub_child.text
            if "artifactId" in sub_child.tag:
                parent_artifactId = sub_child.text
            if "version" in sub_child.tag:
                parent_version = sub_child.text
        parent_key = parent_groupId + "_" + parent_artifactId
        return (parent_key, parent_version)

    @catch_exception
    def get_properties(self, child, pre):
        extra = {}
        for property in child:
            properties_key = property.tag.replace(pre, '')
            properties_value = property.text
            extra[properties_key] = properties_value
        return extra

    def get_dependencies(self, child):
        dependencies = {}
        for dependency in child:
            dependencies_groupId = dependencies_artifactId = dependencies_version = ''
            for sub_child in dependency:
                if "groupId" in sub_child.tag:
                    dependencies_groupId = sub_child.text
                if "artifactId" in sub_child.tag:
                    dependencies_artifactId = sub_child.text
                if "version" in sub_child.tag:
                    dependencies_version = sub_child.text
            key = dependencies_groupId + "_" + dependencies_artifactId
            dependencies[key] = dependencies_version
        return dependencies

    def get_pom_datas(self, pom, project_list, project_name, root):
        parent_extra = {}
        parent_dependencyManagement = {}
        project = eval(project_list)
        for index, path in enumerate(project):
            flag = False
            sub_dependencies = {}
            sub_dependencyManagement = {}
            if '/pom.xml' == path and index == 0:
                flag = True
            realpath = root + project_name + path
            try:
                (sub_key, sub_version, sub_extra, sub_dependencies,
                 sub_dependencyManagement) = self.parse_pom_files(realpath, flag)
                if flag:
                    parent_extra = sub_extra
                    parent_dependencyManagement = sub_dependencyManagement
            except Exception as e:
                print(e, realpath)
            self.preprocessor(
                pom,
                sub_dependencies,
                parent_extra,
                parent_dependencyManagement,
                sub_dependencyManagement)

    def preprocessor(self,
                     pom,
                     dependencies,
                     parent_extra,
                     parent_dependencyManagement,
                     sub_dependencyManagement):
        for key in dependencies.keys():
            if dependencies.get(key):
                continue
            if sub_dependencyManagement.get(key):
                dependencies[key] = sub_dependencyManagement.get(key)
            elif parent_dependencyManagement.get(key):
                dependencies[key] = parent_dependencyManagement.get(key)

        for key in dependencies.keys():
            if not dependencies.get(key):
                continue
            if '$' not in dependencies[key] or '{' not in dependencies[key]:
                continue
            pre_value = dependencies.get(key)

            for each in parent_extra.keys():
                if '${' + each + '}' in pre_value:
                    dependencies[key] = pre_value.replace(
                        '${' + each + '}', parent_extra.get(each))

        for key in dependencies.keys():
            if key not in pom.keys():
                pom[key] = dependencies[key]
            elif dependencies[key] in pom[key]:
                continue
            else:
                pom[key] = pom[key] + '_' + dependencies[key]

    def parse_pom_files(self, content, flag):
        tree = ET.ElementTree()
        tree.parse(content)
        root = tree.getroot()
        pre = root.tag.split('project')[0]
        extra = {}
        dependencies = {}
        dependencyManagement = {}
        main_artifactId = ''
        main_version = ''
        parent_key = ''
        parent_version = ''

        for child in root:
            tag = child.tag.replace(pre, '')
            if 'parent' == tag:
                (parent_key, parent_version) = self.get_parent(child)
            if 'properties' == tag:
                extra = self.get_properties(child, pre)
            if 'artifactId' == tag:
                main_artifactId = child.text
            if 'version' == tag:
                main_version = child.text
            if 'dependencies' == tag:
                dependencies = self.get_dependencies(child)
            if 'dependencyManagement' == tag:
                if len(child) != 1:
                    continue
                dependencyManagement = self.get_dependencies(child[0])

        if flag:
            if main_version:
                if not extra.get('version'):
                    extra['version'] = main_version
                if not extra.get('project.version'):
                    extra['project.version'] = main_version
            if main_artifactId:
                if not extra.get(main_artifactId):
                    extra[main_artifactId] = main_version
            for key in extra.keys():
                if not extra.get(key):
                    continue
                if '$' in extra[key] and '{' in extra[key]:
                    for each in extra.keys():
                        if '${' + each + '}' == extra[key]:
                            extra[key] = extra[each]
            if '$' in parent_version and '{' in parent_version:
                for key in extra.keys():
                    if '${' + key + '}' == parent_version:
                        parent_version = extra[key]
        return (
            parent_key,
            parent_version,
            extra,
            dependencies,
            dependencyManagement)

    @catch_exception
    def post_datas(self, data):
        r = requests.post(
            self.url,
            data=json.dumps(data),
            headers=headers)
        if r.status_code == 400:
            print(self.today,data,str(r.content, 'utf-8'))
            return 
        if r.status_code != 200:
            print(r.status_code)
            print(json.dumps(data))
            raise Exception(str(r.content, 'utf-8'))

    def main_start(self):
        if not self.is_zip_file_exist(self.root_path):
            return
        today_path = self.root_path + os.sep + self.today + os.sep
        result_path = today_path + 'result.txt'
        (project_git, project_pom) = self.get_git_info(result_path)

        for project in project_pom.keys():
            if len(project_git[project].split(
                    '__')) != 2 or not project_git[project].split('__')[0]:
                continue
            pom = {}
            self.get_pom_datas(
                pom, project_pom[project], project, today_path)
            if pom:
                redis_data = self.client.hget(
                    'dependencies', project_git[project])
                if not redis_data or json.loads(redis_data) != pom:
                    self.client.hset(
                        'dependencies',
                        project_git[project],
                        json.dumps(pom))
                    tmp = {}
                    tmp[project_git[project]] = pom
                    tmp['timestamp'] = self.today
                    self.post_datas(tmp)
