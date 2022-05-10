/*
 * Rule.cpp
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

#include <cstdio>
#include <cstdlib>
#include <iostream>
#include "Rule.h"
#include "VeriFlow.h"
#include "EquivalenceClass.h"

using namespace std;

/* deprecated string values
void Rule::initIntValues() {
	for(int i = 0; i < ALL_FIELD_INDEX_END_MARKER; i++)
	{
		if((i == DL_SRC) || (i == DL_DST))
		{
			this->fieldValueInt[i] = ::getMacValueAsInt(this->fieldValue[i]);
			this->fieldMaskInt[i] = ::getMacValueAsInt(this->fieldMask[i]);
		}
		else if((i == NW_SRC) || (i == NW_DST))
		{
			this->fieldValueInt[i] = ::getIpValueAsInt(this->fieldValue[i]);
			this->fieldMaskInt[i] = ::getIpValueAsInt(this->fieldMask[i]);
		}
		else
		{
			this->fieldValueInt[i] = strtoul(this->fieldValue[i].c_str(), NULL, 10);
			this->fieldMaskInt[i] = strtoul(this->fieldMask[i].c_str(), NULL, 10);
		}
	}
	this->locationInt = ::getIpValueAsInt(this->location);
}*/

Rule::Rule()
{
	this->type = DUMMY;

	for(int i = 0; i < ALL_FIELD_INDEX_END_MARKER; i++)
	{
		//this->fieldValue[i] = "0";
		//this->fieldMask[i] = "0";
		this->fieldValueInt[i] = 0;
		this->fieldMaskInt[i] = 0;
	}

	this->wildcards = 0;

	//this->location = "";
	//this->nextHop = "";
	this->locationInt = 0;
	this->nextHopInt = 0;
	this->in_port = 65536;
	this->priority = INVALID_PRIORITY;
	// this->outPort = OFPP_NONE;
	// this->initIntValues();
}

Rule::Rule(const Rule& other)
{
	this->type = other.type;

	for(int i = 0; i < ALL_FIELD_INDEX_END_MARKER; i++)
	{
		//this->fieldValue[i] = other.fieldValue[i];
		//this->fieldMask[i] = other.fieldMask[i];
		this->fieldValueInt[i] = other.fieldValueInt[i];
		this->fieldMaskInt[i] = other.fieldMaskInt[i];
	}
	this->locationInt = other.locationInt;
	this->nextHopInt = other.nextHopInt;

	this->wildcards = other.wildcards;

	//this->location = other.location;
	//this->nextHop = other.nextHop;
	this->in_port = other.in_port;
	this->priority = other.priority;
	// this->outPort = other.outPort;
}

EquivalenceClass Rule::getEquivalenceClass() const
{
	EquivalenceClass rulePacketClass;

	for(int i = 0; i < ALL_FIELD_INDEX_END_MARKER; i++)
	{
		uint64_t fieldValue = this->fieldValueInt[i];
		uint64_t fieldMask = this->fieldMaskInt[i];

		uint64_t maskedFieldValue = fieldValue & fieldMask;

		for(unsigned int j = 0; j < ::fieldWidth[i]; j++)
		{
			rulePacketClass.lowerBound[i] <<= 1;
			rulePacketClass.upperBound[i] <<= 1;

			uint64_t maskBit = (uint64_t)1 << ((unsigned int)(::fieldWidth[i] - 1) - j);
			if((fieldMask & maskBit) == 0) // wildcard bit
			{
				rulePacketClass.upperBound[i] |= 1;
			}
			else
			{
				if((maskedFieldValue & maskBit) == 0) // zero bit
				{
					// do nothing
				}
				else // one bit
				{
					rulePacketClass.lowerBound[i] |= 1;
					rulePacketClass.upperBound[i] |= 1;
				}
			}
		}
	}

	return rulePacketClass;
}

EquivalenceRange Rule::getEquivalenceRange(FieldIndex index) const
{
	EquivalenceRange range;

	uint64_t fieldValue = this->fieldValueInt[index];
	uint64_t fieldMask = this->fieldMaskInt[index];

	uint64_t maskedFieldValue = fieldValue & fieldMask;

	for(unsigned int j = 0; j < ::fieldWidth[index]; j++)
	{
		range.lowerBound <<= 1;
		range.upperBound <<= 1;

		uint64_t maskBit = (uint64_t)1 << ((unsigned int)(::fieldWidth[index] - 1) - j);
		if((fieldMask & maskBit) == 0) // wildcard bit
		{
			range.upperBound |= 1;
		}
		else
		{
			if((maskedFieldValue & maskBit) == 0) // zero bit
			{
				// do nothing
			}
			else // one bit
			{
				range.lowerBound |= 1;
				range.upperBound |= 1;
			}
		}
	}

	return range;
}

bool Rule::equals(const Rule& other) const
{
	for(int i = 0; i < ALL_FIELD_INDEX_END_MARKER; i++)
	{
		if((this->fieldValueInt[i] != other.fieldValueInt[i])
				|| (this->fieldMaskInt[i] != other.fieldMaskInt[i]))
		{
			return false;
		}
	}

	if((this->type == other.type)
			&& (this->wildcards == other.wildcards)
			&& (this->locationInt == other.locationInt)
			&& (this->in_port == other.in_port)
			// && (this->nextHop.compare(other.nextHop) == 0) // Not present in OFPT_FLOW_REMOVED messages.
			&& (this->priority == other.priority)
			// && (this->outPort == other.outPort) // Not used in this version.
	)
	{
		return true;
	}
	else
	{
		return false;
	}
}

bool Rule::operator==(const Rule& other) const
{
	return this->equals(other);
}

uint64_t Rule::operator()() const
{
	uint64_t retVal = 0;
	for(int i = 0; i < ALL_FIELD_INDEX_END_MARKER; i++)
	{
		retVal += this->fieldValueInt[i];
		retVal *= 7; retVal ^= (retVal >> 5);
		retVal += this->fieldMaskInt[i];
		retVal *= 7;
	}
	retVal += this->type;
	retVal *= 7; retVal ^= (retVal >> 5);
	retVal += this->wildcards;
	retVal *= 7; retVal ^= (retVal >> 5);
	retVal += this->locationInt;
	retVal *= 7; retVal ^= (retVal >> 5);
	retVal += this->in_port;
	retVal *= 7; retVal ^= (retVal >> 5);
	// retVal += (int)::getIpValueAsInt(this->nextHop);
	retVal += this->priority;
	retVal *= 7; retVal ^= (retVal >> 5);
	// retVal += this->outPort;
	return retVal;
}

string Rule::toString() const
{
	char buffer[1024];
	sprintf(buffer, "[Rule] type: %d, dlSrcAddr: %s, dlSrcAddrMask: %s, dlDstAddr: %s, dlDstAddrMask: %s, nwSrcAddr: %s, nwSrcAddrMask: %s, nwDstAddr: %s, nwDstAddrMask: %s, location: %s, nextHop: %s, in_port: %u, priority: %u",
			this->type,
			getMacValueAsString(this->fieldValueInt[DL_SRC]).c_str(),
			getMacValueAsString(this->fieldMaskInt[DL_SRC]).c_str(),
			getMacValueAsString(this->fieldValueInt[DL_DST]).c_str(),
			getMacValueAsString(this->fieldMaskInt[DL_DST]).c_str(),
			getIpValueAsString(this->fieldValueInt[NW_SRC]).c_str(),
			getIpValueAsString(this->fieldMaskInt[NW_SRC]).c_str(),
			getIpValueAsString(this->fieldValueInt[NW_DST]).c_str(),
			getIpValueAsString(this->fieldMaskInt[NW_DST]).c_str(),
			getIpValueAsString(this->locationInt).c_str(),
			getIpValueAsString(this->nextHopInt).c_str(), this->in_port, this->priority);

	string retVal = buffer;
	retVal += ", ";

	sprintf(buffer, "wildcards: %u, in_port: %#lx, dl_type: %#lx, dl_vlan: %#lx, dl_vlan_pcp: %#lx, mpls_label: %#lx, mpls_tc: %#lx, nw_proto: %#lx, nw_tos: %#lx, tp_src: %#lx, tp_dst: %#lx",
			this->wildcards, this->fieldValueInt[IN_PORT], this->fieldValueInt[DL_TYPE],
			this->fieldValueInt[DL_VLAN], this->fieldValueInt[DL_VLAN_PCP],
			this->fieldValueInt[MPLS_LABEL], this->fieldValueInt[MPLS_TC],
			this->fieldValueInt[NW_PROTO], this->fieldValueInt[NW_TOS],
			this->fieldValueInt[TP_SRC], this->fieldValueInt[TP_DST]);

	retVal += buffer;
	return retVal;
}
