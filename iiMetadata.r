# \file
# \brief This file contains rules related to metadata
#                       to a dataset
# \author Jan de Mooij
# \copyright Copyright (c) 2016, Utrecht university. All rights reserved
# \license GPLv3, see LICENSE

# \brief GetAvailableValuesForKeyLike Returns list of values that exist in the
# 										icat database for a certain key, which
# 										are like a certain value
#
# \param[in] *key 						Key to look for
# \param[in] *searchString 				String that should be a substring of the
# 										returned values
# \param[in] *isCollection 				Wether to look in collection or data 
# \param[out] *values 					List of possible values for the given key
# 										where the given search string is a substring of
uuIiGetAvailableValuesForKeyLike(*key, *searchString, *isCollection, *values){
	*values = list();

	if(*isCollection){
		foreach(*row in SELECT META_COLL_ATTR_VALUE WHERE 
			META_COLL_ATTR_NAME like '*key' AND
			META_COLL_ATTR_VALUE like '%*searchString%') {
			writeLine("stdout", *row.META_COLL_ATTR_VALUE);
			*values = cons(*row.META_COLL_ATTR_VALUE,*values);
			writeLine("serverLog", *row.META_COLL_ATTR_VALUE);
		}
	} else {
		foreach(*row in SELECT META_DATA_ATTR_VALUE WHERE 
			META_DATA_ATTR_NAME like '*key' AND
			META_DATA_ATTR_VALUE like '%*searchString%') {
			*values = cons(*row.META_DATA_ATTR_VALUE,*values);
		}
	}
}

# /brief iiXSDfroMetadataxml	Locate the XSD to use for a metadata path. Assume $rodsZoneClient is available
# /param[in] metadataxmlpath	path of the metadata XML file that needs to be validated
# /param[out] xsdpath		path of the XSD to use for validation
iiXSDforMetadataxml(*metadataxmlpath, *xsdpath) {
	iiXSDforMetadataxml(*metadataxmlpath, *xsdpath, $rodsZoneClient);
}

# /brief iiXSDforMetadataxml	Locate the XSD to use for a metadata path. Use this rule when $rodsZoneClient is unavailable
# /param[in] metadataxmlpath	path of the metadata XML file that needs to be validated
# /param[out] xsdpath		path of the XSD to use for validation
# /param[in] rodsZone		irods zone to use
iiXSDforMetadataxml(*metadataxmlpath, *xsdpath, *rodsZone) {
	*xsdpath = "";
	*isfound = false;
	uuChopPath(*metadataxmlpath, *metadataxml_coll, *metadataxml_basename);
	foreach(*row in
	       	SELECT USER_GROUP_NAME
	       	WHERE COLL_NAME = *metadataxml_coll
	          AND DATA_NAME = *metadataxml_basename
	          AND USER_GROUP_NAME like "research-%"
		  ) {
		if(!*isfound) {
			*groupName = *row.USER_GROUP_NAME;
			*isfound = true;
	 	} else {
			# Too many query results. More than one group associated with file.
			fail(-54000);
		}
	}

	if (!*isfound) {
		# No results found. Not a research group
		fail(-808000);
	}

	uuGroupGetCategory(*groupName, *category, *subcategory);
	*xsdcoll = "/*rodsZone" ++ IIXSDCOLLECTION;
	*xsdname = "*category.xsd";
	foreach(*row in SELECT COLL_NAME, DATA_NAME WHERE COLL_NAME = *xsdcoll AND DATA_NAME = *xsdname) {
		*xsdpath = *row.COLL_NAME ++ "/" ++ *row.DATA_NAME;
	}
	
	if (*xsdpath == "") {
		*xsdpath = "/*rodsZone" ++ IIXSDCOLLECTION ++ "/" ++ IIXSDDEFAULTNAME;
	}
}
