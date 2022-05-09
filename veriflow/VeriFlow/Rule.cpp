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
}

Rule::Rule()
{
	this->type = DUMMY;

	for(int i = 0; i < ALL_FIELD_INDEX_END_MARKER; i++)
	{
		this->fieldValue[i] = "0";
		this->fieldMask[i] = "0";
	}

	this->wildcards = 0;

	this->location = "";
	this->nextHop = "";
	this->in_port = 65536;
	this->priority = INVALID_PRIORITY;
	// this->outPort = OFPP_NONE;
	this->initIntValues();
}

Rule::Rule(const Rule& other)
{
	this->type = other.type;

	for(int i = 0; i < ALL_FIELD_INDEX_END_MARKER; i++)
	{
		this->fieldValue[i] = other.fieldValue[i];
		this->fieldMask[i] = other.fieldMask[i];
		this->fieldValueInt[i] = other.fieldValueInt[i];
		this->fieldMaskInt[i] = other.fieldMaskInt[i];
	}
	this->locationInt = other.locationInt;

	this->wildcards = other.wildcards;

	this->location = other.location;
	this->nextHop = other.nextHop;
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

int Rule::operator()() const
{
	int retVal = 0;
	for(int i = 0; i < ALL_FIELD_INDEX_END_MARKER; i++)
	{
		retVal += (int)this->fieldValueInt[i] + (int)this->fieldMaskInt[i];
	}

	retVal += this->type;
	retVal += (int)this->wildcards;
	retVal += (int)this->locationInt;
	retVal += this->in_port;
	// retVal += (int)::getIpValueAsInt(this->nextHop);
	retVal += this->priority;
	// retVal += this->outPort;

	return retVal;
}

string Rule::toString() const
{
	char buffer[1024];
	sprintf(buffer, "[Rule] type: %d, dlSrcAddr: %s, dlSrcAddrMask: %s, dlDstAddr: %s, dlDstAddrMask: %s, nwSrcAddr: %s, nwSrcAddrMask: %s, nwDstAddr: %s, nwDstAddrMask: %s, location: %s, nextHop: %s, in_port: %u, priority: %u",
			this->type,
			this->fieldValue[DL_SRC].c_str(), this->fieldMask[DL_SRC].c_str(),
			this->fieldValue[DL_DST].c_str(), this->fieldMask[DL_DST].c_str(),
			this->fieldValue[NW_SRC].c_str(), this->fieldMask[NW_SRC].c_str(),
			this->fieldValue[NW_DST].c_str(), this->fieldMask[NW_DST].c_str(),
			this->location.c_str(), this->nextHop.c_str(), this->in_port, this->priority);

	string retVal = buffer;
	retVal += ", ";

	sprintf(buffer, "wildcards: %u, in_port: %s, dl_type: %s, dl_vlan: %s, dl_vlan_pcp: %s, mpls_label: %s, mpls_tc: %s, nw_proto: %s, nw_tos: %s, tp_src: %s, tp_dst: %s",
			this->wildcards, this->fieldValue[IN_PORT].c_str(), this->fieldValue[DL_TYPE].c_str(),
			this->fieldValue[DL_VLAN].c_str(), this->fieldValue[DL_VLAN_PCP].c_str(),
			this->fieldValue[MPLS_LABEL].c_str(), this->fieldValue[MPLS_TC].c_str(),
			this->fieldValue[NW_PROTO].c_str(), this->fieldValue[NW_TOS].c_str(),
			this->fieldValue[TP_SRC].c_str(), this->fieldValue[TP_DST].c_str());

	retVal += buffer;
	return retVal;
}
