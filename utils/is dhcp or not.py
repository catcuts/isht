
# coding: utf-8

# In[7]:


a="""
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet dhcp
  address 192.168.116.162
  netmask 255.255.255.0
  gateway 192.168.116.1

#allow-hotplug wlan0
#iface wlan0 inet manual
#wpa-roam /etc/wpa_supplicant/wpa_supplicant.conf
#iface default inet dhcp
"""


# In[8]:


import re

lines = a.split("\n")


# In[9]:


lines


# In[10]:


def is_dhcp(lines):
    for i, line in enumerate(lines):
        line = line.strip()
        if line.endswith('eth0'):
            if i < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.endswith('dhcp'):
                    return True
    return False


# In[11]:


is_dhcp(lines)

