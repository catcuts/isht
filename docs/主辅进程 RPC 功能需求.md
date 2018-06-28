# 主辅进程 RPC 功能需求

## 目录

　　[概述](#概述)

　　[主进程 RPC 方法](#主进程-RPC-方法)

　　　　[ping()](#ping%28%29)

　　　　[notice(code, detail)](#notice%28code,-detail%29)

　　　　[restart()](#restart%28%29)

　　　　[discover()](#discover%28%29)

　　　　[reset(type)](#reset%28type%29)

　　　　[onGPIO(pin, type, value)](#onGPIO%28pin,-type,-value%29)

　　[辅助进程 RPC 方法](#辅助进程-RPC-方法)

　　　　[notice(code, detail)](#notice%28code,-detail%29)

　　　　[readGPIO()](#readGPIO%28pin%29)

　　　　[listenGPIO(pin, type)](#listenGPIO%28pin,-type%29)

　　　　[cancelListenGPIO(pin, type)](#cancelListenGPIO%28pin,-type%29)

　　　　[writeGPIO(pin, value)](#writeGPIO%28pin,-value%29)

## 概述

　　**进程定义**

　　１. 工作进程

- 主进程：提供设备信令处理和逻辑处理

- Web 进程: 提供Web服务，包括 API / WebSocket 等访问

　　２. 辅助进程

- 监视工作进程的工作状况，包括 GPIO / 网络配置 / LED / 按键 等

　　**注意：一个辅助进程只能辅助一个主进程**

　　**LED 定义**

<table>
  <thead>
    <tr>
      <th style='text-align: center;'>LED 行为</th>
      <th style='text-align: center;'>适用场景</th>
      <th style='text-align: center;'>备注</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style='text-align: left;'>常灭</td>
      <td style='text-align: left;'>停止工作</td>
      <td>-</td>
    </tr>
    <tr>
      <td style='text-align: left;'>常亮 ————————————————</td>
      <td style='text-align: left;'>正常工作</td>
      <td>-</td>
    </tr>
    <tr>
      <td style='text-align: left;'>长闪 —— —— —— —— —— —— ——</td>
      <td style='text-align: left;'>
- 产品启动中（按下重启键，或正常启动中）<br>
- 发现模式（长按 SET 键 3s 后）<br>
- 恢复出厂密码（长按 RESET 键 5s 后）
      </td>
      <td>-</td>
    </tr>
    <tr>
      <td style='text-align: left;'>短闪 - - - - - - - - - - - - - - - - - - - - - - - - - -</td>
      <td style='text-align: left;'>
 - 产品出错（无任何按键）<br>
 - 恢复出厂数据（长按 RESET 键 10s 后）<br>
 - 恢复程序到上一次升级前（长按 SET + RESET 键 3s 后）
      </td>
      <td>-</td>
    </tr>
  </tbody>
</table>

　　**按键 定义**

<table>
  <thead>
    <tr>
      <th>按键行为</th>
      <th>按键时长</th>
      <th style='text-align: center;'>触发动作</th>
      <th>LED 行为</th>
      <th style='text-align: center;'>备注</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>SET</td>
      <td>＜3s</td>
      <td>重启</td>
      <td>长闪</td>
      <td>重启完毕后，灯复常亮</td>
    </tr>
    <tr>
      <td>SET</td>
      <td>≥3s</td>
      <td>发现模式</td>
      <td>长闪</td>
      <td>-</td>
    </tr>
    <tr>
      <td>RESET</td>
      <td>＜5s</td>
      <td>无</td>
      <td>无</td>
      <td>-</td>
    </tr>
    <tr>
      <td>RESET</td>
      <td>≥5s 且 ＜10s</td>
      <td>恢复出厂密码</td>
      <td>长闪</td>
      <td>-</td>
    </tr>
    <tr>
      <td>RESET</td>
      <td>≥10s</td>
      <td>恢复出厂数据</td>
      <td>短闪</td>
      <td>-</td>
    </tr>
    <tr>
      <td>SET + RESET</td>
      <td>≥3s</td>
      <td>恢复程序到上一次升级前</td>
      <td>短闪</td>
      <td>-</td>
    </tr>
  </tbody>
</table>

　　**RPC 库**

　　https://github.com/hprose/hprose-nodejs#tcp-server-client

## 主进程 RPC 方法

　　供辅助进程远程调用的方法。

### <span style='color: #dd4b39;'>ping()</span>

　　辅助进程调用时，会返回一个计数值。

　　辅助进程应每隔 20 秒调用一次本方法，如果连续失败 8 次，即没有得到应答，则视为主进程已结束。

### <span style='color: #dd4b39;'>notice(code, detail)</span>

　　通知主进程，事件代码：

- 1 = 升级文件下载完毕。主进程应进行一些善后工作，然后返回 0 后正常退出。如果通知 3 次后无法得到有效的应答，则强制结束。

- 2 = 内存不足。  

- 3 = 磁盘空间不足。  
          
### <span style='color: #dd4b39;'>restart()</span>

　　重启工作进程。

### <span style='color: #dd4b39;'>discover()</span>

　　进入发现模式。

### <span style='color: #dd4b39;'>reset(type)</span> 

　　恢复出厂设置。类型：

- 0 = 恢复出厂密码；

- 1 = 恢复出厂数据；

### <span style='color: #dd4b39;'>onGPIO(pin, type, value)</span>

　　通知 listenGPIO 监听相应触发事件类型的主进程

## 辅助进程 RPC 方法

　　供主进程远程调用的方法。

### <span style='color: #dd4b39;'>notice(code, detail)</span>

　　通知辅助进程，事件代码：

- 0 = 主进程已启动完毕。

- 1 = 升级文件等待下载。辅助进程收到后，应前往下载，完毕后告知主进程。

- 2 = 已进入发现模式。
        
- 3 = 错误。

### <span style='color: #dd4b39;'>readGPIO(pin)</span>

　　读取 GPIO 值

### <span style='color: #dd4b39;'>listenGPIO(pin, type)</span>

　　（注意：一个辅助进程只能辅助一个主进程）
  
　　监听 GPIO 触发事件，类型代码：

- 0 = 下升沿

- 1 = 上降沿

### <span style='color: #dd4b39;'>cancelListenGPIO(pin, type)</span>

　　（注意：一个辅助进程只能辅助一个主进程）

　　取消监听 GPIO 触发事件，类型代码：

- 0 = 下升沿

- 1 = 上降沿

### <span style='color: #dd4b39;'>writeGPIO(pin, value)</span>

　　写入 GPIO 值