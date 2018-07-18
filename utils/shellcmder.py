# -*- coding: utf-8 -*-

import os
import subprocess

def _print(line):
    print(line, flush=True)

class MountingError(Exception):
    pass

MOUNT_DEV_ON_POINT = "sudo mount {dev} {point}"
CHECK_POINT_OCCUPIED = "if mountpoint -q {point}; then echo '{point} is occupied'; fi"
CHECK_DEV_MOUNTED_ON_POINT = "df -h | grep '^{dev}.*{point}$'"
UMOUNT_POINT = "sudo umount {point}"

class ShellCommander:

    @staticmethod
    def mount(dev, point, unmount_if_occuppied=True):
        # parameter should be string type
        if not isinstance(dev, str) or not isinstance(point, str):
            err = "cannot mount %s on %s" % (dev, point)
            _print("MountingError: %s" % err)
            raise MountingError(err)

        # point should not be an existing file
        if os.path.isfile(point):
            err = "mounting point <%s> is an existing file, but a directory is required" % point
            _print("MountingError: %s" % err)
            raise MountingError(err)
    
        if os.path.exists(point):  # point is an existing directory
            # but point is not avaialbe(mounted for other drive),
            if ShellCommander.check_point_occupied(point):
                if unmount_if_occuppied:
                    ShellCommander.umount(dev, point)
                    # ShellCommander.mount(dev, point)
                    # return
                else:
                    err = "%s not available for mounting" % point
                    _print("MountingError: %s" % err)
                    raise MountingError(err)
            
            # or this dev has already mounted on this point
            if ShellCommander.check_dev_mounted_on_point(dev, point):
                return True

        else:  # otherwise, make it
            os.makedirs(point)

        cmd = MOUNT_DEV_ON_POINT.format(dev=dev, point=point)

        pipe = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout, stderr = pipe.stdout.read().decode(), pipe.stderr.read().decode()

        if stderr:
            _print("MountingError: %s" % stderr)
            raise MountingError(stderr)
        
        check_mounted = ShellCommander.check_dev_mounted_on_point(dev, point)
        if check_mounted:
            _print("successfully mounted %s on %s" % (dev, point))
            return True
        else:
            err = "failed to mount %s on %s" % (dev, point)
            _print("MountingError: %s" % err)
            raise MountingError(err)

    @staticmethod
    def check_point_occupied(point):
        cmd = CHECK_POINT_OCCUPIED.format(point=point)

        pipe = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout, stderr = pipe.stdout.read().decode(), pipe.stderr.read().decode()
        
        return stdout  # only available will return not None

    @staticmethod
    def check_dev_mounted_on_point(dev, point):
        cmd = CHECK_DEV_MOUNTED_ON_POINT.format(dev=dev, point=point)

        pipe = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout, stderr = pipe.stdout.read().decode(), pipe.stderr.read().decode()
        
        return stdout  # only mounted will return not None

    @staticmethod
    def umount(dev, point):
        cmd = UMOUNT_POINT.format(point=point)

        pipe = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout, stderr = pipe.stdout.read().decode(), pipe.stderr.read().decode()
        
        if stderr:
            _print("Failed to unmount %s from %s: %s" % (dev, point, stderr))
            raise MountingError(stderr)
        else:
            _print("Successfully unmounted %s from %s" % (dev, point))
