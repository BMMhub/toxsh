#!/usr/bin/python

import sys,time
import json

from PyQt5.QtCore import *
from PyQt5.QtNetwork import *

import qtutil
from qtoxkit import *
#from toxsocket import *
from toxtunutils import *
from srudp import *
from httpserver import *


class ToxNetTunSrv(QObject):
    def __init__(self, config_file = './toxtun.ini', parent = None):
        super(ToxNetTunSrv, self).__init__(parent)
        # self.cfg = ToxTunConfig('./toxtun_whttp.ini')
        self.cfg = ToxTunConfig(config_file)
        self.toxkit = None # QToxKit
        self.cons = {}  # peer => con
        self.chans = {} # sock => chan, toxsock => chan, rudp => chan
        #self.host = '127.0.0.1'
        #self.port = 80
        self.chano = 8  # step=2，偶数
        # self.cmdno = 0

        # debug/manager console server
        self.httpd = QHttpServer()
        self.httpd.newRequest.connect(self._mcsrv_newRequest, Qt.QueuedConnection)
        return

    def start(self):
        # toxkit = QToxKit('anon', True)
        tkname = self.cfg.srvname
        toxkit = QToxKit(tkname, True)

        toxkit.connected.connect(self._toxnetConnected)
        toxkit.disconnected.connect(self._toxnetDisconnected)
        toxkit.friendAdded.connect(self._toxnetFriendAdded)
        toxkit.friendConnectionStatus.connect(self._toxnetFriendConnectionStatus)
        toxkit.friendConnected.connect(self._toxnetFriendConnected)
        toxkit.newMessage.connect(self._toxnetFriendMessage)
        
        self.toxkit = toxkit

        ###
        self.httpd.listen(8114, QHostAddress.LocalHost)
        return

    def _toxnetConnected(self):
        qDebug('here')
        toxsock = self.sender()
        #ses = self.cons[toxsock]
        #ses.tox_connected = True

        #ses.sock.readyRead.emit()
        return
    
    def _toxnetDisconnected(self):
        qDebug('here')
        return

    def _toxnetFriendAdded(self, fid):
        qDebug('hehe:' + fid)
        #con = self.toxcons[fid]

        con = ToxConnection()
        con.peer = fid

        self.cons[fid] = con
        
        return

    def _toxnetFriendConnectionStatus(self, fid, status):

        return
    
    def _toxnetFriendConnected(self, fid):
        qDebug('herhe:' + fid)
        # 只重启动srv端时，有可能好友还在线。
        if fid not in self.cons:
            con = ToxConnection()
            con.peer = fid
            self.cons[fid] = con
        
        return

    def _nextChano(self):
        self.chano = self.chano +2
        return self.chano

    def _nextCmdno(self):
        # self.cmdno = self.cmdno +1
        # return self.cmdno
        return

    def _hotfix_resp_clifin1(self, peer, opkt):
        qDebug('here')
        
        ropkt = SruPacket2()
        ropkt.msg_type = 'CLIFIN_ACK'
        ropkt.extra = opkt.extra
        ropkt.seq = opkt.seq
        ropkt.ack = opkt.seq + 1

        # 不知道peer是谁啊，怎么回包呢？
        self.toxkit.sendMessage(peer, ropkt.encode())
        # res = self.transport.send(ropkt.encode())
        # time.sleep(0.0001)
        # self.toxkit.sendMessage(peer, ropkt.encode())
        # res = self.transport.send(ropkt.encode())
        #self.peer_closed = True
        # self.peerClosed.emit()
        # qDebug('emit disconnect event.')
        # self.disconnected.emit()
        return

    def _toxnetFriendMessage(self, friendId, msg):
        qDebug(friendId)
        con = self.cons[friendId]

        tmsg = json.JSONDecoder().decode(msg)
        qDebug(str(tmsg))
        
        opkt = SruPacket2.decode(msg)
        if opkt.msg_type == 'SYN':
            jmsg = opkt.extra
            host = jmsg['host']
            port = jmsg['port']
            
            sock = QTcpSocket()
            sock.setReadBufferSize(1234)
            sock.connected.connect(self._onTcpConnected)
            sock.disconnected.connect(self._onTcpDisconnected)
            sock.readyRead.connect(self._onTcpReadyRead)
            sock.error.connect(self._onTcpError)
            sock.connectToHost(QHostAddress(host), port)

            chan = ToxChannel(con, sock)
            chan.host = host
            chan.port = port
            chan.chanosrv = self._nextChano()
            chan.chanocli = jmsg['chcli']
            # chan.cmdno = jmsg['cmdno']

            self.chans[sock] = chan
            self.chans[chan.chanosrv] = chan

            transport = ToxTunTransport(self.toxkit, chan.con.peer)
            chan.transport = transport
            
            udp = Srudp()
            udp.chano = chan.chanosrv
            chan.rudp = udp
            self.chans[udp] = chan
            udp.setTransport(transport)
            udp.readyRead.connect(self._toxchanReadyRead, Qt.QueuedConnection)
            udp.bytesWritten.connect(self._toxchanBytesWritten, Qt.QueuedConnection)
            udp.disconnected.connect(self._toxchanDisconnected, Qt.QueuedConnection)
            udp.canClose.connect(self._toxchanCanClose, Qt.QueuedConnection)
            udp.peerClosed.connect(self._toxchanPeerClosed, Qt.QueuedConnection)
            udp.timeWaitTimeout.connect(self._toxchanTimeWaitTimeout, Qt.QueuedConnection)

            extra = {'chcli': chan.chanocli, 'chsrv': chan.chanosrv}
            res = udp.buf_recv_pkt(msg, extra)
            # ropkt = udp.buf_recv_pkt(msg)
            # ropkt = SruPacket2.decode(ropkt)
            # ropkt.extra['chano'] = chan.chano
            # ropkt = ropkt.encode()
            # self.toxkit.sendMessage(chan.con.peer, ropkt)
            
            pass
        elif opkt.msg_type == 'CLIFIN':
            jmsg = opkt.extra
            chanosrv = jmsg['chsrv']
            if chanosrv not in self.chans:
                qDebug('pkt -> chan not exists: %d.' % chanosrv)
                # TODO hotfix it
                self._hotfix_resp_clifin1(friendId, opkt)
            else:
                chan = self.chans[jmsg['chsrv']]
                res = chan.rudp.buf_recv_pkt(msg)
            # ropkt = chan.rudp.buf_recv_pkt(msg)
            # self.toxkit.sendMessage(chan.con.peer, ropkt)
        elif opkt.msg_type == 'DATA':
            jmsg = opkt.extra
            chan = self.chans[jmsg['chsrv']]
            res = chan.rudp.buf_recv_pkt(msg)
            # jspkt = chan.rudp.buf_recv_pkt(msg)
            # self.toxkit.sendMessage(chan.con.peer, jspkt)
        else:
            jmsg = opkt.extra
            chanosrv = jmsg['chsrv']
            if chanosrv not in self.chans:
                qDebug('pkt -> chan not exists: %d.' % chanosrv)
            else:
                chan = self.chans[chanosrv]
                res = chan.rudp.buf_recv_pkt(msg)

                    
        # dispatch的过程

        #if jmsg['cmd'] == 'write':
        #    chan = self.chans[jmsg['chano']]
        #    self._tcpWrite(chan, jmsg['data'])
        #    pass

        #if jmsg['cmd'] == 'close':
        #    chano = jmsg['chano']
        #    if chano in self.chans:
        #        chan = self.chans[chano]
        #        self.chans.pop(chano)
        #        chan.sock.close()
        #    pass
        
        return

    # @param data bytes | QByteArray
    def _toxnetWrite(self, chan, data):
        # cmdno = self._nextCmdno()
        # chan.cmdno = cmdno

        extra = {'chsrv': chan.chanosrv, 'chcli': chan.chanocli}
        res = chan.rudp.buf_send_pkt(data, extra)
        # if type(data) == bytes: data = QByteArray(data)

        # extra = {'chano': chan.chano}
        # data = data.toHex().data().decode('utf8')
        # opkt = chan.rudp.buf_send_pkt(data, extra)

        # msg = opkt
        # self.toxkit.sendMessage(chan.con.peer, msg)
        
        return

    def _toxchanReadyRead(self):
        qDebug('here')
        udp = self.sender()
        chan = self.chans[udp]
        
        while True:
            opkt = udp.readPacket()
            if opkt is None: break
            self._tcpWrite(chan, opkt.data)
            
        return

    def _toxchanBytesWritten(self):
        udp = self.sender()
        chan = self.chans[udp]

        chan.sock.readyRead.emit()
        
        return

    def _toxchanDisconnected(self):
        qDebug('here')
        udp = self.sender()

        if udp not in self.chans:
            qDebug('maybe already cleanuped: %d' % udp.chano)
            return
        
        chan = self.chans[udp]
        sock = chan.sock

        chan.rudp_close = True
        self._toxchanPromiseCleanup(chan)
        return
        
        # 清理资源
        if sock not in self.chans: qDebug('sock maybe already closed')
        else: self.chans.pop(sock)

        if udp not in self.chans: qDebug('udp maybe already closed')
        else: self.chans.pop(udp)

        chano = chan.chano
        if chano not in self.chans: qDebug('maybe already closed222')
        else: self.chans.pop(chano)

        qDebug('chans size: %d' % len(self.chans))
        
        return

    def _toxchanCanClose(self):
        qDebug('here')
        
        udp = self.sender()
        chan = self.chans[udp]

        # cmdno = self._nextCmdno()
        extra = {'cmd': 'close', 'chsrv': chan.chanosrv, 'chcli': chan.chanocli, 'cmdno': 0, }
        res = chan.rudp.mkdiscon(extra)
        
        return

    
    def _toxchanPeerClosed(self):
        qDebug('here')
        udp = self.sender()
        chan = self.chans[udp]
        chan.peer_close = True

        self._toxchanPromiseCleanup(chan)
        
        return

    def _toxchanTimeWaitTimeout(self):
        qDebug('here')
        udp = self.sender()

        if udp not in self.chans:
            qDebug('maybe already defered')
            return
        
        chan = self.chans[udp]

        self._toxchanPromiseCleanup(chan)
        return
    
    # promise原理的优雅关闭与清理
    def _toxchanPromiseCleanup(self, chan):
        qDebug('here')
        
        # sock 是否关闭
        # peer 是否关闭
        # srudp的状态是否是CLOSED
        # srudp的TIME_WAIT状态是否超时了

        chan.peer_close = chan.rudp.peer_closed
        promise_results = {
            'peer_close': chan.peer_close,
            'sock_close': chan.sock_close,
            'rudp_close': chan.rudp_close,
        }
        
        nowtime = QDateTime.currentDateTime()
        if chan.rudp.begin_close_time is not None:
            qDebug(str(chan.rudp.begin_close_time.msecsTo(nowtime)))
        if chan.rudp.self_passive_close is False:
            promise_results['active_state'] = (chan.rudp.state == 'TIME_WAIT')
            if chan.rudp.begin_close_time is None:
                promise_results['time_wait_timeout'] = False                
            else:
                duration = chan.rudp.begin_close_time.msecsTo(nowtime)
                promise_results['time_wait_timeout'] = (duration > 15000)
        else:
            promise_results['pasv_state'] = (chan.rudp.state == 'CLOSED')

        promise_result = True
        for pk in promise_results: promise_result = promise_result and promise_results[pk]
        
        if promise_result is True:
            qDebug('promise satisfied: %d<=>%d.' % (chan.chanocli, chan.chanosrv))
        else:
            qDebug('promise noooooot satisfied: %d<=>%d.' % (chan.chanocli, chan.chanosrv))
            qDebug(str(promise_results))
            return

        sock = chan.sock
        udp = chan.rudp

        udp.step_send_timer.stop()
        udp.losspkt_monitor.stop()
        
        # 清理资源
        if sock not in self.chans: qDebug('sock maybe already closed')
        else: self.chans.pop(sock)

        if udp not in self.chans: qDebug('udp maybe already closed')
        else: self.chans.pop(udp)

        chano = chan.chanosrv
        if chano not in self.chans: qDebug('maybe already closed222')
        else: self.chans.pop(chano)

        qDebug('chans size: %d' % len(self.chans))

        return

    def _onTcpConnected(self):
        qDebug('here')

        sock = self.sender()
        chan = self.chans[sock]

        reply = {'cmd': 'connect', 'res': True, 'chcli': chan.chanocli, 'chsrv': chan.chanosrv, 'cmdno': 0, }
        #    self.toxkit.sendMessage(chan.con.peer, reply)
        return
            
    def _onTcpDisconnected(self):
        qDebug('here %d' % len(self.chans))
        sock = self.sender()

        if sock not in self.chans:
            qDebug('maybe already closed123')
            return

        chan = self.chans[sock]
        chan.sock_close = True
        chan.transport.closed = True
        chan.rudp.startCheckClose()
        self._toxchanPromiseCleanup(chan)
        
        return
        chano = chan.chano
        if chano not in self.chans:
            qDebug('maybe already closed222')
            self.chans.pop(sock)
            return

        # cmdno = self._nextCmdno()
        msg = {'cmd': 'close', 'chano': chan.chano, 'cmdno': 0, }

        extra = msg
        chan.transport.closed = True
        chan.rudp.startCheckClose()
        
        #jspkt = chan.rudp.mkdiscon(extra)
        #self.toxkit.sendMessage(chan.con.peer, jspkt)

        return

    def _onTcpError(self, error):
        sock = self.sender()
        qDebug('herhe %s' %  sock.errorString())
        chan = self.chans[sock]
        chano = chan.chanosrv
        chan.transport.closed = True
        
        return
    
        if chano not in self.chans:
            qDebug('maybe already closed333')
            self.chans.pop(sock)
            return

        # cmdno = self._nextCmdno()
        msg = {'cmd': 'close', 'chano': chan.chano, 'cmdno': 0,}
        
        extra = msg
        chan.transport.closed = True
        # chan.rudp.startCheckClose()
        # jspkt = chan.rudp.mkdiscon(extra)
        # self.toxkit.sendMessage(chan.con.peer, jspkt)

        return
    
    def _onTcpReadyRead(self):
        qDebug('here')
        sock = self.sender()
        chan = self.chans[sock]

        peekSize = 897  # 987时就有可能导致超长拆包发送
        extra = {'chcli': chan.chanocli, 'chsrv': chan.chanosrv}
        cnter = 0
        tlen = 0
        while sock.bytesAvailable() > 0:
            #bcc = sock.read(128)
            #self._toxnetWrite(chan, bcc)
            bcc = sock.peek(peekSize)
            # qDebug('%s' % str(bcc))
            # encbcc = chan.transport.encodeData(bcc)
            # res = chan.rudp.attemp_send(encbcc, extra)
            res = chan.rudp.attemp_send(bcc, extra)
            if res is True:
                bcc1 = sock.read(len(bcc))
                chan.rdlen += len(bcc)
                cnter += 1
                tlen += len(bcc)
            else: break
                
        qDebug('XDR: sock->toxnet: %d/%d, %d' % (tlen, chan.rdlen, cnter))
        return

    
    def _tcpWrite(self, chan, data):
        qDebug('hrehe')
        sock = chan.sock

        # rawdata = QByteArray.fromHex(data)
        rawdata = chan.transport.decodeData(data)
        print(rawdata)
        n = sock.write(rawdata)
        chan.wrlen += n
        qDebug('XDR: toxnet->sock: %d/%d' % (n, chan.wrlen))
        
        return


    #####
    def _mcsrv_newRequest(self, req, resp):
        qDebug('here')
        # resp.setHeader('Content-Length', '12')
        # resp.writeHead(200)
        # resp.write('12345\n12345\n')

        cclen = 12
        ccs = []
        ccs.append('12345\n12345\n')

        cc0 = 'chan num: %d/%.2f' % (len(self.chans), len(self.chans)/3.0) + "\n"
        cclen += len(cc0)
        ccs.append(cc0)

        cnter = 0
        for ck in self.chans:
            if type(ck) != QTcpSocket: continue
            chan = self.chans[ck]
            promise_results = self._toxchanPromiseResults(chan)
            # 这儿发现cli端有chan-0出现，有可能是根本没有收到服务器端的SYN2响应包，也就是丢失包了。
            # 而服务器端则没有出现chan-0的现象。
            cc0 = '%d chan-%d/%d: ' % (cnter, chan.chanocli, chan.chanosrv) + str(promise_results) + "\n"
            cclen += len(cc0)
            # resp.write(cc0)
            ccs.append(cc0)
            cnter += 1

        cc0 = 'chan num: %d/%.2f' % (len(self.chans), len(self.chans)/3.0) + "\n"
        cclen += len(cc0)
        ccs.append(cc0)

        resp.setHeader('Content-Length', '%d' % cclen)
        resp.writeHead(200)

        for cc0 in ccs: resp.write(cc0)
        
        resp.end()

        return

    
    # promise原理的优雅关闭与清理
    def _toxchanPromiseResults(self, chan):

        chan.peer_close = chan.rudp.peer_closed
        promise_results = {
            'peer_close': chan.peer_close,
            'sock_close': chan.sock_close,
            'rudp_close': chan.rudp_close,
        }
        
        nowtime = QDateTime.currentDateTime()
        if chan.rudp.begin_close_time is not None:
            qDebug(str(chan.rudp.begin_close_time.msecsTo(nowtime)))
        if chan.rudp.self_passive_close is False:
            promise_results['active_state'] = (chan.rudp.state == 'TIME_WAIT')
            if chan.rudp.begin_close_time is None:
                promise_results['time_wait_timeout'] = False                
            else:
                duration = chan.rudp.begin_close_time.msecsTo(nowtime)
                promise_results['time_wait_timeout'] = (duration > 15000)
        else:
            promise_results['pasv_state'] = (chan.rudp.state == 'CLOSED')

        promise_result = True
        for pk in promise_results: promise_result = promise_result and promise_results[pk]

        promise_results['whole'] = promise_result

        ### some raw status
        promise_results['pasv_close'] = chan.rudp.self_passive_close
        promise_results['state'] = chan.rudp.state
        # promise_results['conn_btime'] = chan.rudp.connect_begin_time
        # promise_results['conn_dtime'] = chan.rudp.connect_begin_time.msecsTo(nowtime)
        promise_results['can_close'] = chan.rudp.can_close

        promise_results['sock_rdlen'] = chan.rdlen
        promise_results['sock_wrlen'] = chan.wrlen

        return promise_results


def main():
    app = QCoreApplication(sys.argv)
    qtutil.pyctrl()

    config_file = './toxtun.ini'
    if len(sys.argv) == 2:
        config_file = sys.argv[1]
        if not os.path.exists(config_file):
            print('config file is not exists: %s' % config_file)
            help()
            sys.exit(1)
    elif len(sys.argv) == 1:
        pass
    else:
        print('provide a valid config file please')
        help()
        sys.exit(1)


    tunsrv = ToxNetTunSrv(config_file)
    tunsrv.start()
    
    app.exec_()
    return


if __name__ == '__main__': main()

