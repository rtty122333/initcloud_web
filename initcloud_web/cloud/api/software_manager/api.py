# coding:utf8

import json
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase

import os
DIRNAME = os.path.abspath(os.path.dirname(__file__))
import ansible_hosts


def execute_tasks(play_name, tasks, hosts, host_list=os.path.join(DIRNAME, 'ansible_hosts.py'), callback="default"):
    # NOTICE: Here is a trick. The host we acquired must in the host list
    # everytime. However I can't get the host list in advance. So I add the
    # hosts into the host list eveytime if it doesn't exist.
    if hosts not in ansible_hosts.hosts["all"]["hosts"]:
        ansible_hosts.hosts["all"]["hosts"].append(hosts)

    # initialize needed objects
    variable_manager = VariableManager()
    loader = DataLoader()

    # create inventory and pass to var manager
    inventory = Inventory(loader=loader, variable_manager=variable_manager, host_list=host_list)
    variable_manager.set_inventory(inventory)

    # create play with tasks
    play_source = dict(
        name=play_name,
        hosts=hosts,
        gather_facts='no',
        tasks=tasks)

    play = Play().load(play_source, variable_manager=variable_manager, loader=loader)

    Options = namedtuple('Options', ['connection', 'module_path', 'forks',
        'become', 'become_method', 'become_user', 'check'])
    options = Options(connection=None, module_path=None, forks=10, become=None,
        become_method=None, become_user=None, check=False)
    passwords = dict()

    # actually run it
    tqm = None
    try:
        tqm = TaskQueueManager(
            inventory=inventory,
            variable_manager=variable_manager,
            loader=loader,
            options=options,
            passwords=passwords,
            stdout_callback=callback)
        return tqm.run(play)
    finally:
        if tqm is not None:
            tqm.cleanup()
        pass


class Config(object):
    dest_dir = r'C:\\ansible\\'
    package_dir = "/root/tmp/"
    package_list = [
        {
            "name": "Microsoft Visual C thingy",
            "filename": r'vcredist_x64.exe',
            "Product_Id": "{CF2BEA3C-26EA-32F8-AA9B-331F7E34BA97}",
            "InstallArguments": "/install /passive /norestart",
            "UninstallArguments": "/uninstall /passive /norestart",
        },
        {
            "name": "Microsoft Visual C thingy",
            "filename": r'vcredist_x86.exe',
            "Product_Id": "{BD95A8CD-1D9F-35AD-981A-3E7925026EBB}",
            "InstallArguments": "/install /passive /norestart",
            "UninstallArguments": "/uninstall /passive /norestart",
        }
    ]


# 1. 获取可安装软件的列表
def get_available_software():
    return Config.package_list


# 2. 获取某个虚拟机已安装软件的列表
LIST_SCRIPT = '''$UninstallKey=”SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall”
#Create an instance of the Registry Object and open the HKLM base key
$reg=[microsoft.win32.registrykey]::OpenRemoteBaseKey(‘LocalMachine’,$computername)
#Drill down into the Uninstall key using the OpenSubKey Method
$regkey=$reg.OpenSubKey($UninstallKey)
#Retrieve an array of string that contain all the subkey names
echo $regkey.GetSubKeyNames()
'''


class InstallResultCallback(CallbackBase):

    def v2_runner_on_ok(self, result, **kwargs):
        self.result = result._result
        self.host = result._host

    def get_result(self):
        return getattr(self, "result", {})


def get_installed_software(hosts):
    callback = InstallResultCallback()
    code = execute_tasks(play_name="List installed software", tasks=[{"raw": LIST_SCRIPT}],
        hosts=hosts, callback=callback)
    return [p["Product_Id"] for p in Config.package_list if p["Product_Id"] in callback.get_result().get("stdout_lines", [])]


# 3. 给指定虚拟机(列表)安装指定的软件(列表)
def install_software(software_list, hosts_list):
    for hosts in hosts_list:
        for software in software_list:
            execute_tasks(play_name="Installing software", tasks=[
                dict(action=dict(module="win_file", args=dict(
                    path=Config.dest_dir,
                    state='directory',
                ))),
                dict(action=dict(module="win_copy", args=dict(
                    src=os.path.join(Config.package_dir, software['filename']),
                    dest=Config.dest_dir,
                ))),
                dict(action=dict(module='win_package', args=dict(
                    name=software["name"],
                    path=Config.dest_dir + software['filename'],
                    Product_Id=software["Product_Id"],
                    Arguments=software["InstallArguments"],
                )), name="Installing " + software["name"])], hosts=hosts)


# 4. 卸载指定虚拟机的指定软件(列表)
def uninstall_software(software_list, hosts_list):
    for hosts in hosts_list:
        for software in software_list:
            execute_tasks(play_name="Uninstalling software", tasks=[
                dict(action=dict(module="win_file", args=dict(
                    path=Config.dest_dir,
                    state='directory',
                ))),
                dict(action=dict(module="win_copy", args=dict(
                    src=os.path.join(Config.package_dir, software['filename']),
                    dest=Config.dest_dir,
                ))),
                dict(action=dict(module='win_package', args=dict(
                    name=software["name"],
                    path=Config.dest_dir + software['filename'],
                    Product_Id=software["Product_Id"],
                    Arguments=software["UninstallArguments"],
                    state="absent",
                )), name="Uninstalling " + software["name"])], hosts=hosts)
