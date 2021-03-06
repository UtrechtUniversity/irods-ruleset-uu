# \file        uuJson.r
# \brief       JSON rules depending on the irods-json-microservices.
# \author      Paul Frederiks
# \copyright   Copyright (c) 2016-2017 Utrecht University. All rights reserved.
# \license     GPLv3, see LICENSE.

# \brief Convert a list of key-value-pair objects into a JSON string.
# \param[in] kvpList	list of key-value-pairs to convert to JSON
# \param[out] json_str	String containing JSON
# \param[out] size	Number of JSON objects in JSON array
#
uuKvpList2JSON(*kvpList, *json_str, *size) {
	*json_str = "[]";
	*size = 0;
	*listsize = size(*kvpList);
	#| writeLine("stdout", *listsize);

	foreach(*kvp in *kvpList) {
		*json_obj = "";
		msi_json_objops(*json_obj, *kvp, "set");
        	msi_json_arrayops(*json_str, *json_obj, "add", *size);
	}
}

# \brief Convert a list of strings into a JSON array.
#
# \param[in] lst  a list of strings
# \param[out] json_str string containing JSON result
#
uuList2JSON(*lst, *json_str) {
	*json_str = "[]";
	*size = 0;
	if (size(*lst) > 0) {
		foreach(*item in *lst) {
			msi_json_arrayops(*json_str, *item, "add", *size);
		}
	}
}
