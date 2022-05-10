/*
 * Network.h
 *
 *  Created on: Mar 15, 2012
 *      Author: khurshid
 *
 * This file is protected by the VeriFlow Research License Agreement
 * available at http://www.cs.illinois.edu/~khurshi1/projects/veriflow/veriflow-research-license-agreement.txt.
 * A copy of this agreement is also included in this package.
 *
 * Copyright (c) 2012-2013 by
 * The Board of Trustees of the University of Illinois.
 * All rights reserved.
 */

#ifndef NETWORK_H_
#define NETWORK_H_

#include <sys/types.h>
#include <unistd.h>
#include <string>
#include <unordered_map>
#include "ForwardingDevice.h"

#define IP_INVALID 0xFFFFFFFFFFFFFFFFul

using namespace std;

class Network
{
private:
	unordered_map< uint64_t, ForwardingDevice > deviceMap;
	unordered_map< uint64_t, uint64_t > idToIpAddressMap;

public:
	bool addDevice(uint64_t id, uint64_t ipAddress, bool endDevice);
	bool addPort(uint64_t ipAddress, unsigned int port, uint64_t nextHopIpAddress);
	uint64_t getNextHopIpAddress(uint64_t ipAddress, unsigned int port);
	bool isEndDevice(uint64_t ipAddress);
	bool isDevicePresent(uint64_t ipAddress) const;
	bool isPortPresent(uint64_t ipAddress, unsigned int port);
	uint64_t getDeviceIpAddress(uint64_t id);
	void print() const;
};

#endif /* NETWORK_H_ */
