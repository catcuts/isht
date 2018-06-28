const shell = require("shelljs");
const SHELL_CMD_GET_TIME_ZONE = "sudo ls -l /etc/localtime | awk '{print $11}' | sed 's/\\/usr\\/share\\/zoneinfo\\///'";
const SHELL_CMD_SET_TIME_ZONE = "sudo ln -sf /usr/share/zoneinfo/{TZ} /etc/localtime";

const SHELL_CMD_GET_NTP_SERVERS = "sudo awk '$1==\"server\"' /etc/ntp.conf";
const SHELL_CMD_CLR_NTP_SERVERS = "sudo sed -i 's/^server.*iburst$/# SERVERS CLEANED/g' /etc/ntp.conf";
const SHELL_CMD_CLR_PALCEHOLDER = "sudo sed -i 's/\\s*#\\s*SERVERS\\s*CLEANED\\s*//g' /etc/ntp.conf";
// const SHELL_CMD_SET_NTP_SERVERS = "sudo sed -i '0,s/\\s*#\\s*SERVERS\\s*CLEANED\\s*/{NTPS}/' /etc/ntp.conf";
const SHELL_CMD_SET_NTP_SERVERS = "sudo sed -i '0,/\\s*#\\s*SERVERS\\s*CLEANED\\s*/s//{NTPS}/' /etc/ntp.conf"

const TIMEOUT_GENERAL = 5000;

const TIMEOUT_GET_TIME_ZONE = 5000;
const TIMEOUT_SET_TIME_ZONE = 5000;
const TIMEOUT_GET_NTP_SERVERS = 5000;

const TIMEOUT_CLR_NTP_SERVERS = 5000;
const TIMEOUT_SET_NTP_SERVERS = 5000;

const SHELL_CMD_CHECK_NTP_SERVERS_EARLIEST = "[ -f /etc/ntp.conf.bkup.earliest ] && echo 1 || echo 0";
const SHELL_CMD_BACKUP_NTP_SERVERS_EARLIEST = "sudo cp /etc/ntp.conf /etc/ntp.conf.bkup.earliest";
const SHELL_CMD_RECOVER_NTP_SERVERS_EARLIEST = "sudo cp -p /etc/ntp.conf.bkup.earliest /etc/ntp.conf";

const SHELL_CMD_BACKUP_NTP_SERVERS = "sudo cp -p /etc/ntp.conf /etc/ntp.conf.bkup";
const SHELL_CMD_RECOVER_NTP_SERVERS = "sudo cp -p /etc/ntp.conf.bkup /etc/ntp.conf";

class LinuxTimeUtils {
    constructor() {
        let _exec = shell.exec(SHELL_CMD_CHECK_NTP_SERVERS_EARLIEST, {silent: true, timeout: TIMEOUT_GENERAL});
        if (parseInt(_exec.stdout) === 0) {
            shell.exec(SHELL_CMD_BACKUP_NTP_SERVERS_EARLIEST, {silent: true, timeout: TIMEOUT_GENERAL});
        }
    }
    getTimeZone() {
        try {
            let _timezone = shell.exec(SHELL_CMD_GET_TIME_ZONE, {silent: true, timeout: TIMEOUT_GENERAL});
        } catch (e) {
            throw new Error("Getting timezone error: Timeout");
        }
        let err = _timezone.stderr;
        if (err) {
            throw new Error("Getting timezone error: " + err);
        } else {
            return _timezone.stdout.replace(/\n$/, "");
        }
    }
    setTimeZone(tz) {
        // note: if tz is not supported, then it fallbacks to UTC timezone
        let _cmd = SHELL_CMD_SET_TIME_ZONE.replace("{TZ}", tz);
        // console.debug("setTimeZone is ready for exec `" + _cmd + "`");
        try {
            let _exec = shell.exec(_cmd, {silent: true, timeout: TIMEOUT_GENERAL});
        } catch (e) {
            throw new Error("Setting timezone error: Timeout");
        }
        let err = _exec.stderr;
        if (err) {
            throw new Error("Setting timezone error: " + err);
        } else if (this.getTimeZone() !== tz) {
            throw new Error("Setting timezone error: not working")
        } else {
            return tz;
        }
    }

    getNTPServers() {
        // in order to get correctly, setting correctly is required
        try {
            let _npt_servers = shell.exec(SHELL_CMD_GET_NTP_SERVERS, {silent: true, timeout: TIMEOUT_GENERAL});
        } catch (e) {
            throw new Error("Getting ntp server error: Timeout")
        }
        let err = _npt_servers.stderr;
        if (err) {
            throw new Error("Getting ntp server error: " + err);
        } else {
            return _npt_servers.stdout.replace(/\n$/, "").split("\n").map(function(x) { return x.replace(/^server\s+/,'').replace(/\s+iburst$/, '') });
        }
    }

    setNTPServers(ntps) {
        if (!Array.isArray(ntps)) { throw new Error("NTP servers should be array") }
        // backup ntp config
        this._backupNTPServers();
        // clear ntp server config
        this._clearNTPServers();

        let new_ntps = ntps.map(function(x) { return "server " + x + " iburst" }).join('\\n');

        let _cmd = SHELL_CMD_SET_NTP_SERVERS.replace("{NTPS}", new_ntps);
        // console.debug("setNTPServers is ready for exec `" + _cmd + "`");
        try {
            let _exec = shell.exec(_cmd, {silent: true, timeout: TIMEOUT_GENERAL});
            if (!_exec.stderr) {
                _exec = shell.exec("/etc/init.d/ntp restart", {silent: false, timeout: 60000});
            }
        } catch (e) {
            throw new Error("Setting ntp error: Timeout");
        }
        let err = _exec.stderr;
        if (err) {
            throw new Error("Setting ntp error: " + err);
        } else {
            this._clearPlaceholder();
            let check_ntps = this.getNTPServers();
            // console.log("ntps requested:\n\t" + ntps.join("\n\t"))
            // console.log("ntps current:\n\t" + check_ntps.join("\n\t"))
            if (ntps.filter(function (x){ return check_ntps.indexOf(x) !== -1 }).length === ntps.length){
                return ntps;
            } else {
                this._recoverNTPServers();
                throw new Error("Setting ntp error: not working, recovered");
            }
        }
    }

    _backupNTPServers() {
        try {
            let _exec = shell.exec(SHELL_CMD_BACKUP_NTP_SERVERS, {silent: true, timeou: TIMEOUT_GENERAL});
        } catch (e) {
            throw new Error("Backupping ntp error: Timeout");
        }
        let err = _exec.stderr;
        if (err) {
            throw new Error("Backupping ntp error: " + err);
        } else {
            return true;
        }
    }

    _clearNTPServers() {
        try {
            let _exec = shell.exec(SHELL_CMD_CLR_NTP_SERVERS, {silent: true, timeout: TIMEOUT_GENERAL});
        } catch (e) {
            throw new Error("Cleaning ntp error: Timeout");
        }
        let err = _exec.stderr;
        if (err) {
            throw new Error("Cleaning ntp error: " + err);
        } else {
            return true;
        }
    }

    _clearPlaceholder() {
        try {
            let _exec = shell.exec(SHELL_CMD_CLR_PALCEHOLDER, {silent: true, timeout: TIMEOUT_GENERAL});
        } catch (e) {
            throw new Error("Cleaning placeholder error: Timeout");
        }
        let err = _exec.stderr;
        if (err) {
            throw new Error("Cleaning placeholder error: " + err);
        } else {
            return true;
        }
    }

    _recoverNTPServers() {
        let timeout = false;
        try {
            let _exec = shell.exec(SHELL_CMD_RECOVER_NTP_SERVERS, {silent: true, timeout: TIMEOUT_GENERAL});
        } catch (e) {
            timeout = true;
        }
        let err = _exec.stderr;
        if (err || timeout) {
            try {  // recovering error results in recovering from the earliest backup
                let _exec = shell.exec(SHELL_CMD_RECOVER_NTP_SERVERS_EARLIEST, {silent: true, timeout: TIMEOUT_GENERAL});
            } catch (e) {
                throw new Error("Recovering ntp error: " + err);
            }
        } else {
            return true;
        }
    }

    // test() {
    //     try {
    //         let meow = shell.exec("echo meow", {silent: true, timeout: 5});
    //         console.log("meow stdout: " + meow.stdout);
    //         console.log("meow stderr: " + meow.stderr);
    //     } catch (e) {
    //         console.log("Getting timezone error: Timeout");
    //     }
    // }
}

// if (false) {
//     try {
//         let tm = new TimeManager();
//
//         console.log("\n========== ========== GETTING TIME ZONE ========== ==========\n")
//
//         console.log("Test getTimeZone: " + tm.getTimeZone());
//
//         console.log("\n========== ========= GETTING NTP SERVERS ========= ==========\n")
//
//         console.log("Test getNTPServers: \n\t" + tm.getNTPServers().join("\n\t"));
//
//         console.log("\n========== ========== SETTING TIME ZONE ========== ==========\n")
//
//         console.log("Test setTimezone: " + tm.setTimeZone("America/Chicago"));
//         console.log("\tcurrent timezone: " + tm.getTimeZone());
//
//         console.log("\n========== ========= SETTING NTP SERVERS ========= ==========\n")
//
//         let ntps = [
//             "0.cn.pool.ntp.org",
//             "1.cn.pool.ntp.org",
//             "2.cn.pool.ntp.org",
//             "3.cn.pool.ntp.org"
//         ];
//         console.log("Test setNTPServers: " + tm.setNTPServers(ntps));
//         console.log("\tcurrent ntp servers: " + tm.getNTPServers());
//     } catch (e) {
//         console.log("Test error:\n" + e.stack)
//     }
//
//     console.log("\n========== =============== E N D =============== ==========\n")
// }


module.exports={
    TimeManager: LinuxTimeUtils
}