# Samuel Jero <sjero@purdue.edu>
# Actual strategy test routines
import manage_vms as mv
import os
import sys
import subprocess
import time
from datetime import datetime
import socket
import struct


from . import system_home, lib_path, config_path, log_path, config
import spur


mininet_config_path = os.path.abspath(os.path.join(system_home, 'mininet_scripts'))
monitor_tools_path = os.path.abspath(os.path.join(system_home, 'monitors'))


class SDNTester:
	def __init__(self, mininet, controllers, log):
		assert(isinstance(mininet, (list,tuple)) and isinstance(controllers, (list,tuple)) and len(mininet) == 1)
		self.mininet = mininet
		self.controllers = controllers
		self.log = log
		self.testnum = 1
		self.msg_types = []
		self.creating_baseline = False
		self.veriflow_flips_threshold = 10
		self.veriflow_flips = 0
		self.veriflow_output = []
		self.rule_state = []
		self.rule_state_baseline = []

	def baseline(self, test_script):
		self.creating_baseline = True
		num = self.testnum
		self.veriflow_flips = []

		#Do Baseline
		for i in range(0,3):
			self.testnum = 0
			res = self.doTest(test_script, ["*,*,*,*,*,CLEAR,*"])
			if res[0] == False:
				print "Warning!!! Baseline failed!!!"

		#Process Results
		self.veriflow_flips_threshold = (sum(self.veriflow_flips)/len(self.veriflow_flips))*2	#VeriFlow Flip Threshold
		self.testnum = num
		self.creating_baseline = False

		#Log Thresholds
		decor = '$' * 40 + ' Thresholds ' + '$' * 40 + '\n'
		self.log.write(decor)
		self.log.write("Veriflow Flips: %i\n" % (self.veriflow_flips_threshold))
		self.log.write("Rule State: (%i)\n" % (len(self.rule_state_baseline)))
		for r in self.rule_state_baseline:
			self.log.write(r + "\n")
		self.log.write(decor)
		self.log.flush()

	def retrieve_feedback(self):
		return {'msg_types':self.msg_types}

	def doTest(self,test_script, strategy):
		result = [True, "Sucess!"]
		self.log.write("##############################Starting Test " + str(self.testnum) + "###################################\n")
		self.log.write(str(datetime.today()) + "\n")
		#Create Address/Port strings
		controlleraddrs = list()
		proxyaddrs = list()
		proxyports = list()
		for c in self.controllers:
			controlleraddrs.append(mv.vm2ip(c) + ":" + str(config.controller_port))
			proxyaddrs.append(config.proxy_addr + ":" + str(config.proxy_base_port + c))
			proxyports.append(str(config.proxy_base_port + c))

		#Start Controllers
		if self._start_controllers() == False:
			return (False,"System Failure")

		#Start Proxy
		proxy = self._start_proxy(controlleraddrs, proxyports)
		if proxy is None:
			self._stop_controllers()
			return (False, "System Failure")
		
		#Send Proxy Strategy
		if self._send_proxy_strategy(strategy, proxyports) == False:
			self._stop_controllers()
			proxy.terminate()
			return (False, "System Failure")

		#VeriFlow
		veriflow = None
		if config.veriflow_enabled == True:
			vf_port = config.veriflow_base_port + self.controllers[0]
			veriflow = self._start_veriflow(test_script, proxyports, vf_port)
			proxyaddrs = list()
			proxyaddrs.append(config.proxy_addr + ":" + str(vf_port))
			if veriflow is None:
				self._stop_controllers()
				proxy.terminate()
				return(False, "System Failure")

		#Do Test
		test_std_err = None
		res, test_std_err = self._call_test(test_script, proxyaddrs)
		if res is None:
			self._stop_controllers()
			if veriflow is not None:
				veriflow.terminate()
			proxy.terminate()
			return (False, "System Failure")

		#Evaluate Results
		if  isinstance(res, (dict)) and "results" in res:
			res_list = res["results"]
			for r in res_list:
				if r == False:
					result[0] = False
					result[1] = "Network Tests"

			#Check Rules
			if "rules" in res:
				if self._check_rule_dump(res["rules"]) == False:
					result[0] = False
					result[1] = "Network State"
		else:
			result[0] = False
			result[1] = "System Failure"
		
		#Check Message Types
		if self._get_msg_types(("localhost",config.proxy_com_port + self.mininet[0])) == False:
			if veriflow is not None:
				veriflow.terminate()
			proxy.terminate()
			self._stop_controllers()
			return (False, "System Failure")
		if self._check_for_error_msgs():
			result[0] = False
			result[1] = "Error Message"

		#Check and Stop VeriFlow
		if config.veriflow_enabled:
			if self._stop_veriflow(veriflow) == False:
				proxy.terminate()
				self._stop_controllers()
				return (False, "System Failure")
			res = self._check_veriflow_results()
			if result[0] == True:
				result = res

		#Stop Proxy
		if self._stop_proxy(proxy) == False:
			self._stop_controllers()
			return (False, "System Failure")

		#Stop Controllers
		self._stop_controllers()

		#Cleanup Any Mininet Remnants
		self._cleanup()

		#Log
		self.log.flush()
		self.log.write("*****************\n")
		self.log.write("********* Test Script output ********\n")
		if test_std_err:
			self.log.write(test_std_err)
		self.log.write("*****************\n")
		self.log.write("Veriflow Flips: %s\n" %(str(self.veriflow_flips)))
		self.log.write("*****************\n")
		if result[0] == False and result[1] == "VeriFlow":
			self.log.write("VeriFlow Output:\n")
			for f in self.veriflow_output:
				self.log.write(f + "\n")
			self.log.write("*****************\n")
		self.log.write("Rule State:\n")
		for r in self.rule_state:
			self.log.write(r + "\n")
		self.log.write("Num: %d\n" % (len(self.rule_state)))
		self.log.write("*****************\n")
		self.log.write("Message Types Seen: %s\n" % (str(self.msg_types)))
		self.log.write("*****************\n")
		self.log.write("Test Result: " + str(result[0]) + " , Reason:" + str(result[1]) + "\n")
		self.log.write(str(datetime.today()) + "\n")
		self.log.write("##############################Ending Test " + str(self.testnum) + "###################################\n")
		self.log.flush()
		self.testnum+=1
		return result


	def startVms(self):
		for c in self.controllers:
			mv.startvm(c)
		for m in self.mininet:
			mv.startvm(m)
		for c in self.controllers:
			if(self._waitListening(mv.vm2ip(c),22,240,True)==False):
				print "Error: Controller VM %d not started!" % (c)
				return False
			else:
				os.system("scp -p -i %s -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -r %s %s@%s:~\n" % (config.vm_ssh_key, monitor_tools_path, config.controller_user, mv.vm2ip(c)))
				shell = spur.SshShell(hostname=mv.vm2ip(c), username = config.controller_user, missing_host_key=spur.ssh.MissingHostKey.accept,private_key_file=config.vm_ssh_key)
				proc = shell.run(["/bin/bash","-i" ,"-c", "cd monitors && make clean && make"])
				if proc.return_code is not 0:
					print "Error: Make failed!"
					return False
		for m in self.mininet:
			if(self._waitListening(mv.vm2ip(m),22,240,True)==False):
				print "Error: Mininet %d not started!" % (c)
				return False
			else:
				if config.mininet_replace_scripts:
					os.system("scp -p -i %s -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -r %s/* %s@%s:~\n" % (config.vm_ssh_key, mininet_config_path, config.mininet_user, mv.vm2ip(m)))
					os.system("scp -p -i %s -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -r %s %s@%s:~\n" % (config.vm_ssh_key, monitor_tools_path, config.mininet_user, mv.vm2ip(m)))
					shell = spur.SshShell(hostname=mv.vm2ip(m), username = config.mininet_user, missing_host_key=spur.ssh.MissingHostKey.accept,private_key_file=config.vm_ssh_key)
					proc = shell.run(["/bin/bash","-i" ,"-c", "cd monitors && make clean && make"])
					if proc.return_code is not 0:
						print "Error: Make failed!"
						return False
		return True

	def stopVms(self):
		for c in self.controllers:
			mv.stopvm(c)
		for m in self.mininet:
			mv.stopvm(m)

	def _start_proxy(self, controlleraddrs, proxyports):
		proxy = None
		ts = time.time()
		cmd = config.proxy_path + " -p " + str(config.proxy_com_port + self.mininet[0])
		for c in range(0,len(controlleraddrs)):
			cmd = cmd + " -c " +  proxyports[c] + ":" + controlleraddrs[c]
		self.log.write("Proxy CMD: " + cmd + "\n")
		self.log.write("********* Proxy output ********\n")
		self.log.flush()
		try:
			proxy = subprocess.Popen(cmd, shell = True, stdout = self.log, stderr = subprocess.STDOUT)
		except Exception as e:
			print e
			self.log.write("Exception: " + str(e) + "\n")
			self.log.flush()
			return None
		if(self._waitListening("localhost",config.proxy_com_port + self.mininet[0],60)==False):
			self.log.write("Proxy failed to start after 60 seconds\n")
			self.log.flush()
			return None
		if config.enable_stat:
			self.log.write('[timer] Start proxy: %d sec.\n' % (time.time() - ts))
		return proxy

	def _start_veriflow(self, test_script, proxyports, vf_port):
		assert(len(self.controllers)==1)
		veriflow = None
		ts = time.time()
		topo_file = config.veriflow_topo_path + os.path.splitext(os.path.basename(test_script.format(controllers="").strip()))[0] + ".vft"
		log_file = config.veriflow_log_path + config.veriflow_log_name.format(instance=self.mininet[0])
		cmd = config.veriflow_path + " " + str(vf_port) + " 127.0.0.1  " + proxyports[0] + " " + topo_file + " " + log_file
		self.log.write("Veriflow CMD: " + cmd + "\n")
		self.log.flush()
		try:
			veriflow = subprocess.Popen(cmd, shell = True, stdout = self.log, stderr = subprocess.STDOUT)
		except Exception as e:
			print e
			self.log.write("Exception: " + str(e) + "\n")
			self.log.flush()
			return None
		if(self._waitListening("localhost",config.veriflow_base_port + self.controllers[0],60)==False):
			self.log.write("Veriflow failed to start after 60 seconds\n")
			self.log.flush()
			return None
		if config.enable_stat:
			self.log.write('[timer] Start VeriFlow: %d sec.\n' % (time.time() - ts))
		return veriflow

	def _start_controllers(self):
		ts = time.time()
		for c in self.controllers:
			shell = spur.SshShell(hostname=mv.vm2ip(c), username=config.controller_user, missing_host_key=spur.ssh.MissingHostKey.accept, private_key_file=config.vm_ssh_key)
			res = shell.run(["/bin/bash","-i" ,"-c", "~/monitors/control.sh {0} {1}".format(config.controller_type, "start")])
			self.log.write("Starting Controller (" + mv.vm2ip(c) + ")...\n" + res.output)
			self.log.flush()
		for c in self.controllers:
			if(self._waitListening(mv.vm2ip(c),config.controller_port,60)==False):
				self.log.write("Controller %s failed to start after %d seconds" % (mv.vm2ip(c),60))
				self.log.flush()
				return False
			else:
				# Controller starts.
				res = shell.run(["/bin/bash","-i" ,"-c", "~/monitors/control.sh {0} {1}".format(config.controller_type, "mon")])
				self.log.write("Starting resource monitor for controller (" + mv.vm2ip(c) + ")...\n" + res.output)
				self.log.flush()
		if config.enable_stat:
			self.log.write('[timer] Start all controllers: %d sec.\n' % (time.time() - ts))
		return True

	def _call_test(self, test_script, proxyaddrs):
		ts = time.time()
		res = None
		proc = None
		m = self.mininet[0]
		shell = spur.SshShell(hostname=mv.vm2ip(m), username = config.mininet_user, missing_host_key=spur.ssh.MissingHostKey.accept,private_key_file=config.vm_ssh_key)
		self.log.write("Starting Test: " + test_script.format(controllers=" ".join(proxyaddrs)) + "\n")
		self.log.flush()
		try:
			proc = shell.run(["/bin/bash","-i" ,"-c", test_script.format(controllers=" ".join(proxyaddrs))])
			res = eval(proc.output)
		except Exception as e:
			print e
			self.log.write("Exception: " + str(e) + "\n")
			self.log.flush()
			return (None, None)
		if config.enable_stat:
			self.log.write('[timer] Do all tests: %d sec.\n' % (time.time() - ts))
		return (res, proc.stderr_output)

	def _stop_controllers(self):
		ts = time.time()
		for c in self.controllers:
			shell = spur.SshShell(hostname=mv.vm2ip(c), username = config.controller_user, missing_host_key=spur.ssh.MissingHostKey.accept,private_key_file=config.vm_ssh_key)
			try:
				self.log.write("Stopping controller (" + mv.vm2ip(c) + ")...\n")
				res = shell.run(["/bin/bash","-i" ,"-c", "~/monitors/control.sh {0} {1}".format(config.controller_type, "stop")], allow_error=True)
				self.log.write(res.output)
			except Exception as e:
				print e
				self.log.write("Exception: " + str(e) + "\n")
				self.log.flush()
				return False
		# time.sleep(config.controller_stop_time)
		# for c in self.controllers:
		# 	shell = spur.SshShell(hostname=mv.vm2ip(c), username = config.controller_user, missing_host_key=spur.ssh.MissingHostKey.accept,private_key_file=config.vm_ssh_key)
		#	try:
		#		res = shell.run(["/bin/bash","-i" ,"-c", "~/monitors/control.sh {0} {1}".format(config.controller_type, "kill")], allow_error=True)
		#		# res = shell.run(["/bin/bash","-i" ,"-c", config.controller_kill_cmd], allow_error=True)
		#		if res.return_code == 0:
		#			print "Controller still running!"
		#			self.log.write("Controller still running!\n")
		#			self.log.flush()
		#			return False
		#	except Exception as e:
		#		print e
		#		self.log.write("Exception: " + str(e) + "\n")
		#		self.log.flush()
		#		return False
		if config.enable_stat:
			self.log.write('[timer] Stop controllers: %d sec.\n' % (time.time() - ts))
		return True

	def _stop_proxy(self, proxy):
		ts = time.time()
		if proxy.poll() is not None:
			print "Proxy has crashed!!!\n"
			self.log.write("Proxy has crashed!!!\n")
			self.log.flush()
			return False
		proxy.terminate()
		if config.enable_stat:
			self.log.write('[timer] Stop proxy: %d sec.\n' % (time.time() - ts))
		return True

	def _stop_veriflow(self, veriflow):
		ts = time.time()
		if config.veriflow_enabled:
			if veriflow.poll() is not None:
				print "VeriFlow has crashed!!!\n"
				self.log.write("VeriFlow has crashed!!!\n")
				self.log.flush()
				return False
			veriflow.send_signal(2)
		if config.enable_stat:
			self.log.write('[timer] Stop VeriFlow: %d sec.\n' % (time.time() - ts))
		return True

	def _cleanup(self):
		ts = time.time()
		shell = spur.SshShell(hostname=mv.vm2ip(self.mininet[0]), username = config.mininet_user, missing_host_key=spur.ssh.MissingHostKey.accept,private_key_file=config.vm_ssh_key)
		res = shell.run(["/bin/bash","-i" ,"-c", config.mininet_cleanup_cmd])
		if config.enable_stat:
			self.log.write('[timer] Clean up mininet: %d sec.\n' % (time.time() - ts))
		return True

	def _send_proxy_strategy(self, strategy, proxyports):
		ts = time.time()
		for l in strategy:
			if type(l) != str:
				return False
			cmd = l.format(controllers=proxyports)
			self.log.write("Strategy CMD: " + cmd + "\n")
			self.log.flush()
			res = self._proxy_communicate(("localhost",config.proxy_com_port + self.mininet[0]), cmd)
			if (res == False):
				self.log.write("Failed to Send Command\n")
				self.log.flush()
				return False
		if config.enable_stat:
			self.log.write('[timer] Send strategy: %d sec.\n' % (time.time() - ts))
		return True

	def _waitListening(self,host='127.0.0.1', port=80, timeout=None, output=False):
		"""Wait until server is listening on port.
		returns True if server is listening"""
		cmd = ('echo A | telnet -e A %s %s' % ( host, port ))
		start = time.time()
		result = ""
		try:
			result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
		except subprocess.CalledProcessError as e:
			pass
		while 'Connected' not in result:
			if 'No route' in result:
				return False
			if timeout and time.time() >= start + timeout:
				print 'could not connect to %s on port %d' % (host, port )
				return False
			if output:
				print 'waiting for ' + host + ' to listen on port ' + str(port)
			time.sleep(0.5)
			try:
				result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
			except subprocess.CalledProcessError as e:
				pass
		if output:
			print host + " is listening on " + str(port)
			return True

	def _proxy_communicate(self,addr, msg, wait_for_response = False):
		rsp = ""

		#Connect
		try:
			sock = socket.create_connection(addr)
		except Exception as e:
			self.log.write("Failed to connect to to proxy(%s:%d): %s\n" % (addr[0], addr[1], e))
			self.log.flush()
			return False

		#Buid command
		snd = struct.pack("!H",len(msg) + 2)
		snd += msg

		#Send command
		sock.send(snd)

		if wait_for_response:
			#Wait for Length
			data = ""
			while (len(data) < 3):
				data = sock.recv(4,socket.MSG_PEEK)
				if len(data) == 0:
					sock.close()
					return False
				
			
			#compute length
			try:
				length = struct.unpack("!H",data[0:2])
				length = length[0]
			except Exception as e:
				sock.close()
				return False
			
			#Receive Message
			msg = ""
			mlen = length
			while(len(msg) < mlen):
				data = sock.recv(length)
				if len(data) == 0:
					sock.close()
					return False
				msg += data
				length -= len(data)

			#Process Message
			rsp = msg[2:]

		#Close Socket
		sock.close()
		if wait_for_response:
			return rsp
		return True

	def _get_msg_types(self, addr):
		resp = self._proxy_communicate(addr,"*,*,*,*,*,PKT_TYPES,*",wait_for_response = True)
		if type(resp) is bool and resp == False:
			print "Error: Failed to get message type feedback from proxy!"
			self.log.write("Error: Failed to get message type feedback from proxy!\n")
			self.log.flush()
			return False
		self.msg_types = resp.split(",")
		while '' in self.msg_types:
			self.msg_types.remove('')
		return True

	def _check_for_error_msgs(self):
		for t in self.msg_types:
			if "error_msg" in t:
				return True
		return False

	def _check_veriflow_results(self):
		log_file = config.veriflow_log_path + config.veriflow_log_name.format(instance=self.mininet[0])
		
		#Open Log
		f = open(log_file, "r")
		if not f:
			print "Error: Failed to open VeriFlow log: %s" % (log_file)
			self.log.write("Error: Failed to VeriFlow log: %s\n" % (log_file))
			self.log.flush()
			return (False, "System Error")
		log = f.readlines()
		f.close()
		self.veriflow_output = log

		#Process Log
		working = True
		flips = 0
		for line in log:
			if line.find("Network Broken!") > 0:
				working = False
				flips += 1
			if line.find("Network Fixed!") > 0:
				working = True
		
		
		#Determine Results
		if self.creating_baseline:
			self.veriflow_flips.append(flips)
		else:
			self.veriflow_flips = flips
			if (flips > self.veriflow_flips_threshold):
				return (False, "VeriFlow")
		if working is not True:
			return (False, "VeriFlow")
		return (True, "Success!")

	def _check_rule_dump(self,raw):
		state = []

		if isinstance(raw, (list,tuple)) == False:
			return False
		for sw in raw:
				if isinstance(sw, (str)) == False:
					return False
				sw_name = ""
				lines = sw.splitlines()
				for ln in lines:
					#Grab Switch Name
					if ln.find("NXST_FLOW") > 0:
						csv = ln.split(",")
						sw_name = csv[0]
						continue
					#Clean other fields
					csv = ln.split(",")
					cleaned = sw_name + ","
					has_data = False
					for v in csv:
						if v.find("packets") > 0:
							continue
						if v.find("bytes") > 0:
							continue
						if v.find("used") > 0:
							continue
						if v.find("duration") > 0:
							continue
						if v.find("idle") > 0:
							continue
						if v.find("cookie") > 0:
							continue
						if v == "":
							continue
						cleaned = cleaned + v + ","
						has_data = True
					if has_data:
						state.append(cleaned)
		state.sort()

		if self.creating_baseline:
			if len(self.rule_state_baseline) == 0:
				self.rule_state_baseline = state
			else:
				#Merge and remove non-deterministic config
				new_baseline = []
				for s in self.rule_state_baseline:
					if s in state:
						new_baseline.append(s)
				self.rule_state_baseline = new_baseline
		else:
			#Save state
			self.rule_state = state

			#Compare State
			for s in self.rule_state_baseline:
				if s not in state:
					return False
		return True
