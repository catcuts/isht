# -*- coding: utf-8 -*-

import os
import hashlib

def md5_from_file(filename):
    """
    用于获取文件的 md5
    :param filename: 文件名
    :return: MD5
    """
    if not os.path.isfile(filename):  # 如果校验md5的文件不是文件，返回空
        # print("[  error  ] %s not a file !" % filename)
        return ""
    md5hash = hashlib.md5()
    f = open(filename, 'rb')
    while True:
        b = f.read(8096)
        if not b:
            break
        md5hash.update(b)   
    f.close()
    return md5hash.hexdigest().lower()

def md5_from_string(string):
    """
    用于获取字符串的 md5
    :param string: 字符串
    :return: MD5
    """
    md5hash = hashlib.md5()
    md5hash.update(string.encode('utf-8'))
    return md5hash.hexdigest().lower()

if __name__ == "__main__":

    e = "./test/prog_update/eventbus.js"
    m = "./test/prog_update/manager.js"
    s = "./test/prog_update/server.js"

    e_md5 = md5_from_file(e)
    m_md5 = md5_from_file(m)
    s_md5 = md5_from_file(s)

    x = s_md5 + m_md5 + e_md5

    x_md5 = md5_from_string(x)

    print(x_md5)