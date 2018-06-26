var async = require('async')
const hprose = require("hprose")

// default_config = {
//     "rpc_server": "http://127.0.0.1:8181/",
//     "port": 8282,
//     "logfile": "./simu_server_log"
// }

var default_config = {
    "rpc_server": "tcp://127.0.0.1:7000/",
    "local_rpc_server": "tcp://127.0.0.1:7000/",
    "logfile": "./simu_server_log"
}

var UPDATE_PKG_URL = "https://github.com/catcuts/isht/raw/updatepkg/vigserver.zip"

var RESET_TYPE = {
    0: "user passwd",
    1: "user data"
}

// notice codes from master process
var MASTER_READY_FOR_UPDATE = 0
var MASTER_RESTARTED = true
var MASTER_RESETTED = true

var MASTER_PROCESS_STARTED = 0
var UPDATE_READY_FOR_DOWNLOAD = 1
var DISCOVER_MODE_ACTIVATED = 2
var DISCOVER_MODE_DEACTIVATED = 3
var MASTER_PROCESS_ERROR = 4

// nocice codes to master process
var UPDATE_PACKAGE_DOWNLOADED = 1
var INSUFFICIENT_MEMORY = 2
var INSUFFICIENT_SPACE = 3


/**
 * 替换所有匹配exp的字符串为指定字符串
 * @param exp 被替换部分的正则
 * @param newStr 替换成的字符串
 */
String.prototype.replaceAll = function (exp, newStr) {
	return this.replace(new RegExp(exp, "gm"), newStr);
};

/**
 * 原型：字符串格式化
 * @param args 格式化参数值
 */
String.prototype.format = function(args) {
	var result = this;
	if (arguments.length < 1) {
		return result;
	}

	var data = arguments; // 如果模板参数是数组
	if (arguments.length == 1 && typeof (args) == "object") {
		// 如果模板参数是对象
		data = args;
	}
	for ( var key in data) {
		var value = data[key];
		if (undefined != value) {
			result = result.replaceAll("\\{" + key + "\\}", value);
		}
	}
	return result;
}


class Respond {
    constructor() {
        this.payload = null
    }
}


class Simulator {
    constructor(config) {
        this.config = config || {}
        Object.assign(this.config, default_config)

        this.rpc_server = config.rpc_server
        this.client = hprose.Client.create(this.rpc_server)

        this.local_rpc_server = config.port
        this.server = hprose.Server.create(this.local_rpc_server)

        this.server.addFunctions([
            this.ping,
            this.notice,
            this.restart,
            this.discover,
            this.reset,
            this.onGPIO,
            this.progress
        ])

        this.simulator_stop = false
        this.pid = null

        this.logfile = config.logfile

        this.print("[  SI-INFO  ] Simulator initialized : \n" + JSON.stringify(config))
    }

    start() {
        // this.start_simulating()
        try {
            this.pid = process.pid()
            this.server.start()
        } catch (e) {
            this.print("[  MO-ERROR  ] Local rpc server failed to start : " + e)
        }
    }

    start_simulating() {
        setTimeout(this._start_simulating, 2000)
    }

    _start_simulating() {
        var tasks = []
        tasks.push(function(callback) {
            this.print("[  SI-INFO  ] <SIMULATING> MASTER STARTING ...")
            setTimeout(function() {  
                callback(null);
                this.print("[  SI-INFO  ] <SIMULATING> MASTER STARTED .")
            }, 2000); 
        })

        tasks.push(function() {
            if (this.try_notify(args=[MASTER_PROCESS_STARTED, {}])) {
                this.print("[  SI-INFO  ] SUCCESSFULLY NOTIFIED .")
            } else {
                this.print("[  SI-INFO  ] FAILED TO NOTIFIED .")
            }
        })

        tasks.push(function(callback) {
            this.print("[  SI-INFO  ] <SIMULATING> MASTER NEED UPDATING ...")
            setTimeout(function() {  
                callback(null);
                this.print("[  SI-INFO  ] <SIMULATING> MASTER UPDATE PACKAGE READY FOR DOWNLOAD .")
            }, 2000); 
        })

        tasks.push(function() {
            if (this.try_notify(args=(UPDATE_READY_FOR_DOWNLOAD, {
                "url": UPDATE_PKG_URL
            }))) {
                this.print("[  SI-INFO  ] SUCCESSFULLY NOTIFIED .")
            } else {
                this.print("[  SI-INFO  ] FAILED TO NOTIFIED .")
            }
        })

        async.waterfall(task, function(err, result){  
            if (err) return this.print("[  SI-ERROR  ] SIMULATING ERROR: " + err);  
        })  
    }

    try_notify(number_of_try=0, interval=1, args=[], respond=null) {
        if (number_of_try < 0) { return }

        var _respond = respond
        var respond = respond || new Respond()

        var tasks = []

        tasks.push(function(callback) {
            try {
                respond.payload = this.client.notice(...args)
                number_of_try = -1
            } catch (e) {
                respond.payload = null
                setTimeout(function() {
                    callback(null)
                    number_of_try --
                    this.try_notify(number_of_try, interval, args, respond)
                }, interval)
            }
        })

        async.waterfall(task, function(err, result){  
            if (err) return this.print("[  SI-ERROR  ] TRY_NOTIFY ERROR: " + err);  
        }) 

        while ((_respond === null) && (number_of_try >= 0)) {
            try {
                respond.payload = this.client.notice(...args)
            } catch (e) {
                remain_times = ("REMIANED " + number_of_try)
                this.print("[  SI-INFO  ] <SIMULATING> CONNECTION REFUSED . TRYING ... " + remain_times)
                number_of_try --
            }
        }

        return respond.payload
    }

    // @RPC  
    ping() {
        this.print("[  SI-INFO  ] Simulator received a `ping` .")
        return this.pid
    }

    // @RPC  
    notice(code, detail=null) {
        detail = detail || {}
        if (code === UPDATE_PACKAGE_DOWNLOADED) {
            this.print("[  SI-INFO  ] Simulator received a notice: update package downloaded .")
            // time.sleep(2)  // simulating the costing time before getting ready
            return MASTER_READY_FOR_UPDATE
        } else if (code === INSUFFICIENT_MEMORY) {
            return this.print("[  SI-INFO  ] Simulator received a notice: insufficient memory .")
        } else if (code === INSUFFICIENT_SPACE) {
            return this.print("[  SI-INFO  ] Simulator received a notice: insufficient space .")
        }
    }

    // @RPC            
    restart() {
        this.print("[  SI-INFO  ] Simulator restarted .")
        return MASTER_RESTARTED
    }

    // @RPC            
    discover() {
        this.print("[  SI-INFO  ] Simulator in discover mode .")

        setTimeout(function disable_discover() {
            this.print("[  SI-INFO  ] Simulator quit discover mode .")
            this.notice(DISCOVER_MODE_DEACTIVATED, detail={})
        }, 5000)

        return DISCOVER_MODE_ACTIVATED
    }

    // @RPC            
    reset(type=-1) {
        this.print("[  SI-INFO  ] Simulator reset: %s" % RESET_TYPE.get(type, "unknown"))
        return MASTER_RESETTED
    }

    // @RPC
    onGPIO(pin, type, value) {
        return this.print("[  SI-INFO  ] Simulator GPIO event .")
    }

    // @RPC
    progress(progress, message, code) {
        if (code) {
            var status = "Normal"  
        } else {
            var status = "Abnormal"
        }
        return this.print("[  SI-INFO  ] Progress from Assistant: {0} {1} (status: {2})".format(progress, message, status))
    }

    // @LOCAL
    print(logline, screen=False) {  
        console.log(logline)  
        // with open(this.logfile, "a") as f:
        //     print(logline, file=f)
        //     if screen: print(logline)
    }
}

simulator = new Simulator(default_config)
simulator.start()