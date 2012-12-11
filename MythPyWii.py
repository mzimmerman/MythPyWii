#!/usr/bin/env python2
"""
Copyright (c) 2008, Benjie Gillam
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
    * Neither the name of MythPyWii nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
# By Benjie Gillam https://github.com/benjie/MythPyWii

'''
Created on Nov 3, 2009
@author: mzimmerman
'''

# Note to self - list of good documentation:
# cwiid: http://flx.proyectoanonimo.com/proyectos/cwiid/
# myth telnet: http://www.mythtv.org/wiki/index.php/Telnet_socket

import socket, asynchat, asyncore, time, cwiid, logging, os, thread, subprocess
from math import atan, cos

#logging.basicConfig(filename="/dev/stdout", level=logging.DEBUG)

logger = logging.getLogger("mythpywii")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

popen = subprocess.Popen(args="ps -uf | grep MythPyWii.py | grep -v grep", shell=True, stdout=subprocess.PIPE)
psoutput = popen.communicate()[0]
pid = os.getpid()
#logger.debug("os.getpid() = " + str(pid))
#logger.debug("popen.pid = " + str(popen.pid))
#logger.debug("psoutput = " + psoutput)
for line in psoutput.splitlines():
    if line.split()[1] not in str(pid) and line.split()[1] not in str(popen.pid):
        logger.info("MythPyWii already running under pid " + line.split()[1])
        exit()

def do_scale(input, max, divisor=None):
    if divisor is None: divisor = max
    if (input > 1): input = 1
    if (input < -1): input = -1
    input = int(input * divisor)
    if input>max: input = max
    elif input < -max: input = -max
    return input

class MythSocket(asynchat.async_chat):
    '''
    classdocs
    '''
    def __init__(self, addr="localhost", port=6546, handler=None):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((addr,port))
        asynchat.async_chat.__init__(self, sock=s)
        self.handler = handler
        self.ibuffer = []
        self.obuffer = ""
        self.set_terminator("\r\n")
        
    def found_terminator(self):
        global wc
        message = self.ibuffer.pop()
	logger.debug("from Myth: " + message)
        if (message[:17] == "Playback Recorded" or message[:12] == "Playback DVD" or message[:14] == "Playback Video"):
	    if (message.count("pause") == 0 ): 
		#Playback Recorded 7:41 of 33:55 pause 5021 2012
        	wc.lastaction = time.time()
		logger.debug("Still playing content, reset the time")
	    # else - content paused, do nothing and let it timeout
        self.ibuffer = []
        
    def collect_incoming_data(self, data):
        """Buffer the data"""
        self.ibuffer.append(data)
    
    def cmd(self, data, log=True):
        self.push(data + "\n")
        logger.debug("sending command " + data);
        if log:
            global wc
            wc.lastaction = time.time()
            #logger.debug("reset lastaction")
        
class WiiController(object):
    #Initialize variables
    wm = None
    reportvals = {"accel":cwiid.RPT_ACC, "button":cwiid.RPT_BTN, "ext":cwiid.RPT_EXT,  "status":cwiid.RPT_STATUS}
    report={"accel":True, "button":True}
    state = {"acc":[0, 0, 1]}
    lasttime = 0.0
    laststate = {}
    responsiveness = 0.15
    firstPress = True
    firstPressDelay = 0.5
    maxButtons = 0
    
    def rumble(self):
        self.wm.rumble=1
        time.sleep(.2)
        self.wm.rumble=0
    
    def wii_rel(self, v, axis):
        return float(v - self.wii_calibration[0][axis]) / (
        self.wii_calibration[1][axis] - self.wii_calibration[0][axis])

    def wmcb(self, messages,timeout="0"):
        state = self.state
        global ms
        for message in messages:
            if message[0] == cwiid.MESG_BTN:
                state["buttons"] = message[1]
            #elif message[0] == cwiid.MESG_STATUS:
            #    print "\nStatus: ", message[1]
            elif message[0] == cwiid.MESG_ERROR:
                if message[1] == cwiid.ERROR_DISCONNECT:
                    closeWiimote()
                    continue
                else:
                    print "ERROR: ", message[1]
            elif message[0] == cwiid.MESG_ACC:
                state["acc"] = message[1]
            else:
                print "Unknown message!", message
            laststate = self.laststate
            #print "B: %d/%d %d          \r" % (state["buttons"],self.maxButtons,self.ms.ok()),
            #sys.stdout.flush()
            if ('buttons' in laststate) and (laststate['buttons'] <> state['buttons']):
                if state['buttons'] == 0:
                    self.maxButtons = 0
                elif state['buttons'] < self.maxButtons:
                    continue
                else:
                    self.maxButtons = state['buttons']
                self.lasttime = 0
                self.firstPress = True
            if (self.wm is not None) and (state["buttons"] > 0) and (time.time() > self.lasttime+self.responsiveness):
                self.lasttime = time.time()
                wasFirstPress = False
                if self.firstPress:
                    wasFirstPress = True
                    self.lasttime = self.lasttime + self.firstPressDelay
                    self.firstPress = False
                # Stuff that doesn't need roll/etc calculations
                if state["buttons"] == cwiid.BTN_HOME:
                    ms.cmd('key escape')
                if state["buttons"] == cwiid.BTN_A:
                    ms.cmd('key enter')
                if state["buttons"] == cwiid.BTN_B:
                    ms.cmd('key escape')
                if state["buttons"] == cwiid.BTN_MINUS:
                    ms.cmd('key d')
                if state["buttons"] == cwiid.BTN_UP:
                    ms.cmd('key up')
                if state["buttons"] == cwiid.BTN_DOWN:
                    ms.cmd('key down')
                if state["buttons"] == cwiid.BTN_LEFT:
                    ms.cmd('key left')
                if state["buttons"] == cwiid.BTN_RIGHT:
                    ms.cmd('key right')
                if state["buttons"] == cwiid.BTN_PLUS:
                    ms.cmd('key p')
                if state["buttons"] == cwiid.BTN_1:
                    ms.cmd('key i')
                if state["buttons"] == cwiid.BTN_2:
                    ms.cmd('key m')
            self.laststate = state.copy() #NOTE TO SELF: REMEMBER .copy() !!!

    def __init__(self):
        self.wm = cwiid.Wiimote()
        logger.info("Connected to a wiimote :)")
        # Wiimote calibration data (cache this)
        self.wii_calibration = self.wm.get_acc_cal(cwiid.EXT_NONE)
        self.wm.led = cwiid.LED1_ON | cwiid.LED4_ON
        self.wm.rpt_mode = sum(self.reportvals[a] for a in self.report if self.report[a])
        self.wm.enable(cwiid.FLAG_MESG_IFC | cwiid.FLAG_REPEAT_BTN)
        self.wm.mesg_callback = self.wmcb
        self.lastaction = time.time()
        
def closeWiimote():
    logger.info("About to close connection to the Wiimote")
    global wc, ms
    if wc is not None:
        if wc.wm is not None:
            wc.wm.close()
            wc.wm = None
        wc = None
    if ms is not None:
        ms.close()
        ms = None

def main():
    logger.info("Press 1&2 on the Wiimote")
    global wc, ms
    ms = None
    wc = None
    while True:
        while (wc is None):
            try:
                wc = WiiController()
                wc.rumble()
                logger.info("Forcing on the display and connecting to Myth")
                ms = MythSocket()
		ms.cmd(data = "key underscore", log = False)
                logger.debug("MythSocket has been created")
                thread.start_new_thread(asyncore.loop,())
            except Exception, errMessage:
                closeWiimote()
        #logger.debug("lastaction = " + str(wc.lastaction))
        #logger.debug("time.time() = " + str(time.time()))
        #logger.debug("difference = " + str(wc.lastaction - time.time()))
        if wc.lastaction < time.time() - 30:
            ms.cmd(data = "query location", log = False)
        if wc.lastaction < time.time() - 60:
            #2100 seconds is 35 minutes
            #1200 seconds is 20 minutes
            logger.info("1 minute has passed since last action or playing, disconnecting Wiimote")
            closeWiimote()
        time.sleep(5)

main()
