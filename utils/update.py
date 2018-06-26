# -*- coding: utf-8 -*-
import os  
import sys
import shutil 
import zipfile 
import re
import hashlib
import stat
import time
import traceback

class UpdateManager:

    def __init__(self,src,dist,bkup=None,bkup_file_name=None,log=None):

        self.src = src # 升级源文件（zip 压缩包）
        self.dist = dist # 升级目标目录
        self.bkup = bkup or (dist + "_bkup") # 备份目录
        self.bkup_file_name = bkup_file_name
        self.log = log or (dist + "_updating-log") # 日志目录
        self.status = "idle"
        self.errors = []

        if self.bkup and self.bkup_file_name:
            self._bkup = os.path.join(self.bkup,self.bkup_file_name)
        else:
            self._bkup = "(NOT REQUIRED)"
        self.printl("initializing...\n\tsrc: %s\n\tdist: %s\n\tbkup: %s\n\tlog: %s" %(self.src,self.dist,self._bkup,self.log))

    # 解压升级包（ zip 格式）  
    def un_zip(self): # file_name 是包含了 zip 压缩包文件名的文件路径
        self.status = "unzipping"  
        self.printl("\nunzip processing...")
        try:
            src = self.src
            zip_file = zipfile.ZipFile(src,"r")  # 创建一个 zipFile 实例（ zip 压缩包对象）

            dist = src + "_unzipped"
            # dist = re.sub(r"\.zip$","",src) # 解压目标目录

            if os.path.isdir(dist): # 判断解压目标目录（ [dist]_files ）是否存在 
                self.printl("dist already existed: %s" %(dist))  # 存在则无需创建目标目录
            else:  
                os.mkdir(dist) # 不存在则创建目标目录  
                self.printl("new a dist")
            
            for names in zip_file.namelist():  # 遍历 zip 压缩包中的所有文件
                zip_file.extract(names,dist + "/")  # 并将它们解压到目标目录（已测试为同步操作）

            zip_file.close()  # 关闭该压缩包对象

            unZipSuccess = True

        except Exception as error:
            self.printl("zip file handling error: %s" %error)
            unZipSuccess = False
            
        except KeyboardInterrupt:
            self.printl("unzip interrupted by someone")
            unZipSuccess = False

        if unZipSuccess:
            filePaths = self.filePaths = self.getFilePaths(dist)
            self.printl("unzip success:\nfilePaths: ( total %d )" %len(filePaths))
            for index, path in enumerate(filePaths):
                self.printl("%d\t%s" %(index + 1,path))
        else:
            self.errors.append("failed to unzip")

        return self.errors

    def zip(self,rootDir):
        if not os.path.isdir(self.bkup):
            os.mkdir(self.bkup)
        
        bkup_file_name = self.bkup_file_name
        if not bkup_file_name: return True
        if bkup_file_name == "$TIME$":
            bkup_file_name = time.strftime('%Y%m%d_%H%M%S',time.localtime(time.time()))

        bkup_file_path = os.path.join(self.bkup,bkup_file_name)
        bkup_file_path = bkup_file_path if bkup_file_path.endswith('.zip') else (bkup_file_path + '.zip')
        if os.path.isfile(bkup_file_path): os.remove(bkup_file_path)
        try:
            f = zipfile.ZipFile(bkup_file_path,'w',zipfile.ZIP_DEFLATED) 
            for root, dirs, files in os.walk(rootDir): 
                for fileName in files: 
                    f.write(os.path.join(root,fileName),os.path.join(root.replace(rootDir,""),fileName)) 
            f.close()
            zipSuccess = True
        except Exception as error:
            self.printl("zip file handling error: %s" %error)
            zipSuccess = False
        except KeyboardInterrupt:
            self.printl("unzip interrupted by someone")
            zipSuccess = False

        if not zipSuccess:
            self.errors.append("failed to zip")

        return zipSuccess

    # 获得升级包内所有文件路径列表
    def getFilePaths(self,rootDir):
        filePaths = []
        for root,dirs,files in os.walk(rootDir): 
            # self.printl("root:%s\n\tdirs:%s\n\tfiles:%s" %(root,dirs,files))
            for fileName in files:
                filePaths.append(os.path.join(root,fileName))
        return filePaths

    # 升级
    # -备份-> src -解压 -> src_unzipped/...A -(...A)替换(...B)-> dist/...B -校验-> -恢复/完成->
    # 示例：python update.py some_Disk:\path\to\src.zip some_other_Disk:\some_path\to\src (not "src\")
    # 实例：python update.py D:\Documents\catcuts\project\iot_raspberrypi\iptalk0.3.7-7.10补丁\src.zip D:\Documents\catcuts\project\iot_raspberrypi\iptalk_v0.3.6\src
    def update(self):
        def del_rw(action, path, exc): # 用于删除只读文件，如 .git
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)

        src = self.src + "_unzipped"
        dist = self.dist
        bkup = self.bkup

        # -------------------------------  backup  -------------------------------
        self.status = "backup"
        self.printl("\nbackup starting...")
        if self.zip(dist):  # 压缩目标文件(夹)dist
            self.printl("backup compelete at %s" %bkup)
            bkupError = False
        else:
            self.printl("backup failed at %s" %bkup)
            bkupError = True
            self.errors.append("failed to backup")
        # if os.path.isdir(bkup): 
        #     self.printl("bkup already existed: %s will be whole covered" %(bkup))  
        #     shutil.rmtree(bkup, onerror=del_rw) # 删除 bkup
        # else:  
        #     self.printl("new a bkup: %s" %bkup)
        # os.mkdir(bkup) 
        # if self.copyFiles(dist,bkup):
        #     self.printl("backup compelete.")
        #     bkupError = False
        # else:
        #     self.printl("backup failed.")
        #     bkupError = True
        #     self.errors.append("failed to backup")

        # -------------------------------  update  -------------------------------
        if not bkupError:
            self.status = "update"
            self.printl("\nupdating...\ntarget: %s" %dist)
            if self.copyFiles(src,dist):
                self.printl("update compelete.")
            else:
                self.printl("update failed.\n\ntarget recovering...")
                self.recover()

        self.printl("\nrelated info: ")
        self.printl("\tsrc: %s" %self.src)
        self.printl("\tdist: %s" %self.dist)
        self.printl("\tbkup: %s" %self._bkup)
        self.printl("\tlog: %s" %self.log)
        self.printl("\terrors: %s" %self.errors)

        return self.errors

    def recover(self):
        def del_rw(action, path, exc): # 用于删除只读文件，如 .git
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)

        dist = self.dist
        bkup = self.bkup
        self.status = "recovery"
        self.printl("recovering...")
        shutil.rmtree(dist, onerror=del_rw) # 删除 dist(partly updated)
        if self.copyFiles(bkup,dist):
            self.printl("recover compelete.")
        else:
            self.printl("recover failed: %s\nyou may need to manually recover.")
            self.errors.append("failed to recover")

    # 取得文件 MD5 值
    def getFileMD5(self,filepath):  
        if os.path.isfile(filepath):
            md5obj = hashlib.md5()
            maxbuf = 8192
            f = open(filepath,'rb')
            while True:
                buf = f.read(maxbuf)
                if not buf:
                    break
                md5obj.update(buf)
            f.close()
            hash = md5obj.hexdigest()
            return str(hash).upper()
        return None    

    def copyFiles(self,src,dist): # <src>\<ff> -> <dist>\<ff>
        count = 0
        for root,dirs,files in os.walk(src):
            targetRoot = root.replace(src,dist)
            if not os.path.isdir(targetRoot):
                os.makedirs(targetRoot)
            for fileName in files:
                count+=1
                sourceFilePath = os.path.join(root,fileName)
                targetFilePath = os.path.join(targetRoot,fileName)

                self.printl("%d\tcopying %s file...\n\t\tfrom %s\n\t\tto %s" %(count,self.status,sourceFilePath,targetFilePath))    

                try:
                    shutil.copy(sourceFilePath,targetFilePath)
                except Exception as error:
                    self.printl("copy failed: %s" %error)
                    return False
                except KeyboardInterrupt as error:
                    self.printl("copy Interrupted by someone: %s" %error)
                    return False

                if os.path.isfile(targetFilePath) and self.getFileMD5(sourceFilePath) == self.getFileMD5(targetFilePath):
                    self.printl("\tcopy success")
                else:
                    self.printl("\tcopy failed: MD5 check is not ok by an unexpected error.")
                    return False
        return True

    # 打印到日志
    def printl(self,logline):
        logtime = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
        logline = "[%s]%s" % (logtime, logline)

        log = self.log
        status = self.status
        logfile = os.path.join(log,"log.txt")
        if not os.path.isdir(log):
            os.makedirs(log)
        if status == "idle":
            with open(logfile,"w") as f:
                print(logline,file=f)
                print(logline)
        else:
            with open(logfile,"a") as f:
                print(logline,file=f)
                print(logline)

if __name__ == "__main__":
    """"
    @param: <src>, <dist>
    """
    src = ""
    dist = ""

    try:
        src = sys.argv[1]
        dist = sys.argv[2]
        if not re.search(r".zip$",src) or not os.path.isfile(src):
            print("update terminated: source is not a .zip file")
            updateEnable = False
        elif not os.path.isdir(dist):
            print("update terminated: target is not a directory")
            updateEnable = False
        else:
            updateEnable = True
    except:
        print("zipfile source or target is unspecified")
        updateEnable = False

    if updateEnable:
        updateManager = UpdateManager(src,dist) # 实例化
        updateManager.un_zip() # 解压
        updateManager.update() # 更新
        # updateManager.recover() # 还原
