# \file      iiPolicyChecks.r
# \brief     Helper function to check for policy pre and post conditions
#            used by the locking mechanism and the folder status transition mechanism.
# \author    Paul Frederiks
# \author    Lazlo Westerhof
# \copyright Copyright (c) 2016-2018, Utrecht University. All rights reserved.
# \license   GPLv3, see LICENSE.

## XXX: JSON refactor: No replacement for this yet.
##
## \brief Rename invalid XSD when added to a systemcollection
##        to prevent breakage of the metadata form editor.
##
## \param[in] xmlpath         Path of XSD file added to a systemcollection
## \param[in] xsdpath         Path to XSD to check against
##
#iiRenameInvalidXML(*xmlpath, *xsdpath) {
#		*invalid = false;
#		iiValidateXml(*xmlpath, *xsdpath, *err, *msg);
#		if (*err != 0) {
#			writeLine("serverLog", "iiRenameInvalidXML: *msg");
#			writeLine("serverLog", "Renaming corrupt or invalid $objPath");
#			msiGetIcatTime(*timestamp, "unix");
#			*iso8601 = uuiso8601(*timestamp);
#			msiDataObjRename(*xmlpath, *xmlpath ++ "_invalid_" ++ *iso8601, 0, *status_rename);
#		}
#}

# \brief Check validity of requested folder status transition in a research area.
#
# \param[in] fromstatus    folder status before requested transition
# \param[in] tostatus      folder status after requested transition
#
iiIsStatusTransitionLegal(*fromstatus, *tostatus) {
	*legal = false;
	# IIFOLDERTRANSTIONS should be defined in iiConstants.r and lists all the legal status transitions
	foreach(*legaltransition in IIFOLDERTRANSITIONS) {
		(*legalfrom, *legalto) = *legaltransition;
		if (*legalfrom == *fromstatus && *legalto == *tostatus) {
			*legal = true;
			break;
		}
	}
	*legal;
}

# \brief Check validity of requested status transition in the vault.
#
# \param[in] fromstatus    folder status before requested transition
# \param[in] tostatus      folder status after requested transition
#
iiIsVaultStatusTransitionLegal(*fromstatus, *tostatus) {
	*legal = false;
	foreach(*legaltransition in IIVAULTTRANSITIONS) {
		(*legalfrom, *legalto) = *legaltransition;
		if (*legalfrom == *fromstatus && *legalto == *tostatus) {
			*legal = true;
			break;
		}
	}
	*legal;
}

# \brief Return a list of locks on an object.
#
# \param[in] objPath  path of collection or data object
# \param[out] locks   list of locks with the rootCollection of each lock as value
#
iiGetLocks(*objPath, *locks) {
	*locks = list();
	*lockattrname = IILOCKATTRNAME;
	msiGetObjType(*objPath, *objType);
	if (*objType == '-d') {
		uuChopPath(*objPath, *collection, *dataName);
		foreach (*row in SELECT META_DATA_ATTR_VALUE
					WHERE COLL_NAME = *collection
					  AND DATA_NAME = *dataName
					  AND META_DATA_ATTR_NAME = *lockattrname
			) {
				*rootCollection= *row.META_DATA_ATTR_VALUE;
				*locks = cons(*rootCollection, *locks);
			}
	} else {
		foreach (*row in SELECT META_COLL_ATTR_VALUE
					WHERE COLL_NAME = *objPath
					  AND META_COLL_ATTR_NAME = *lockattrname
			) {
				*rootCollection = *row.META_COLL_ATTR_VALUE;
				*locks = cons(*rootCollection, *locks);
		}
	}
}


# \brief Check if user metadata can be modified.
#
# \param[in] option          parameter of the action passed to the PEP. 'add', 'set' or 'rm'
# \param[in] itemType        type of item (-C for collection, -d for data object)
# \param[in] itemName        name of item (path in case of collection or data object)
# \param[in] attributeName   attribute name of AVU
# \param[out] allowed        boolean to indicate if the action is allowed
# \param[out] reason         reason the action is not allowed\
#
iiCanModifyUserMetadata(*option, *itemType, *itemName, *attributeName, *allowed, *reason) {
	*allowed = false;
	*reason = "Unknown error";

	iiGetLocks(*itemName, *locks);
	if (size(*locks) > 0) {
		if (*itemType == "-C") {
			foreach(*rootCollection in *locks) {
				if (strlen(*rootCollection) > strlen(*itemName)) {
					*allowed = true;
					*reason = "Lock found, but in subcollection *rootCollection";
				} else {
					*allowed = false;
					*reason = "Lock found, starting from *rootCollection";
					break;
				}
			}
		} else {
			*reason = "Locks found. *locks";
		}
	} else {
		*allowed = true;
		*reason = "No locks found";
	}

	#DEBUG writeLine("serverLog", "iiCanModifyUserMetadata: *itemName; allowed=*allowed; reason=*reason");
}

# \brief iiCanModifyOrgMetadata   currently all modifications on organisational metadata is controlled by ACL's.
#                                 If locked folder would disallow the modification of the lock,
#                                 it would not be possible to remove the lock
#
# \param[in] option          parameter of the action passed to the PEP. 'add', 'set' or 'rm'
# \param[in] itemType        type of item (-C for collection, -d for data object)
# \param[in] itemName        name of item (path in case of collection or data object)
# \param[in] attributeName   attribute name of AVU
# \param[out] allowed   boolean to indicate if the action is allowed
# \param[out] reason    reason the action is not allowed
#
iiCanModifyOrgMetadata(*option, *itemType, *itemName, *attributeName, *allowed, *reason) {
	*allowed = true;
	*reason = "No reason to lock OrgMetatadata yet";
	#DEBUG writeLine("serverLog", "iiCanModifyOrgMetadata: *itemName; allowed=*allowed; reason=*reason");
}

# \brief Prevent illegal folder status modifications.
#
# \param[in] option         parameter of the action performed on the folder status metadata. 'rm', 'add' or 'set'
# \param[in] path           path of folder
# \param[in] attributeName  (new) attribute name of AVU
# \param[in] attributeValue (new) attribute value of AVU
# \param[in] actor          user name of actor
# \param[out] allowed       boolean to indicate if the action is allowed
# \param[out] reason        reason the action is not allowed
#
iiCanModifyFolderStatus(*option, *path, *attributeName, *attributeValue, *actor, *allowed, *reason) {
	*allowed = false;
	*reason = "Unknown error";
	if (*attributeName != IISTATUSATTRNAME) {
		*reason = "Called for attribute *attributeName instead of FolderStatus.";
		succeed;
	}

	if (*option == "rm") {
		*transitionFrom = *attributeValue;
		*transitionTo =  FOLDER;
	}

	if (*option == "add") {
		iiFolderStatus(*path, *transitionFrom);
		*transitionTo = *attributeValue;

	}

	if (*option == "set") {
		iiFolderStatus(*path, *transitionFrom);
		*transitionTo = *attributeValue;
	}

	# All metadata actions can be checked with the same function
	iiCanTransitionFolderStatus(*path, *transitionFrom, *transitionTo, *actor, *allowed, *reason);

	#DEBUG writeLine("serverLog", "iiCanModifyFolderStatus: *path; allowed=*allowed; reason=*reason");
}

# \brief Check if metadata modification with the mod action is allowed.
#
# \param[in] option             parameter of the action performed on the folder status metadata. always 'mod'
# \param[in] path               path of folder
# \param[in] attributeName      current attribute name of AVU
# \param[in] attributeValue     current attribute value of AVU
# \param[in] newAttributeName   new attribute name of AVU
# \param[in] newAttributeValue  new attribute value of AVU
# \param[in] actor              user name of actor
# \param[out] allowed           boolean to indicate if the action is allowed
# \param[out] reason            reason the action is not allowed
#
iiCanModifyFolderStatus(*option, *path, *attributeName, *attributeValue, *newAttributeName, *newAttributeValue, *actor, *allowed, *reason) {
	*allowed = false;
	*reason = "Unknown error";
	if (*newAttributeName == "" || *newAttributeName == IISTATUSATTRNAME ) {
		*transitionFrom = *attributeValue;
		*transitionTo = triml(*newAttributeValue, "v:");
		iiCanTransitionFolderStatus(*path, *transitionFrom, *transitionTo, *actor, *allowed, *reason);
	} else {
		*reason = "*attributeName should not be changed to *newAttributeName";
	}

	#DEBUG writeLine("serverLog", "iiCanModifyFolderStatus: *path; allowed=*allowed; reason=*reason");
}

# \brief Check if a research folder status transition is legal.
#
# \param[in] folder
# \param[in] transitionFrom  current status to transition from
# \param[in] transitionTo    new status to transition to
# \param[out] allowed        boolean to indicate if the action is allowed
# \param[out] reason         reason the action is not allowed
#
iiCanTransitionFolderStatus(*folder, *transitionFrom, *transitionTo, *actor, *allowed, *reason) {
	*allowed = false;
	*reason = "Unknown error";
	if (iiIsStatusTransitionLegal(*transitionFrom, *transitionTo)) {
		*allowed = true;
		*reason = "Legal status transition. *transitionFrom -> *transitionTo";
	} else {
		if (*transitionFrom == FOLDER) {
			*reason = "Illegal status transition. Current folder has no status.";
		} else {
			*reason = "Illegal status transition. Current status is *transitionFrom.";
		}
		succeed;
	}

	if (*transitionTo == SUBMITTED) {
			*metadataJsonPath = *folder ++ "/" ++ IIJSONMETADATA;
			if (!uuFileExists(*metadataJsonPath)) {
					*allowed = false;
					*reason = "Metadata missing, unable to submit this folder.";
					succeed;
			} else {
					*status     = "";
					*statusInfo = "";
					rule_uu_meta_validate(*metadataJsonPath, *status, *statusInfo);
					if (*status != "0") {
							*allowed = false;
							*reason = "Metadata is invalid, please check metadata form.";
							succeed;
					}
			}
	}

	if (*transitionTo == ACCEPTED || *transitionTo == REJECTED) {
		*groupName = "";
		*err1 = errorcode(rule_uu_collection_group_name(*folder, *groupName));
		*err2 = errorcode(uuGroupGetCategory(*groupName, *category, *subcategory));
		*err3 = errorcode(uuGroupExists("datamanager-*category", *datamanagerExists));
		if (*err1 < 0 || *err2 < 0 || *err3 < 0) {
			*allowed = false;
			*reason = "Could not determine if datamanager-*category exists";
			succeed;
		}
		if (*datamanagerExists) {
			uuGroupGetMemberType("datamanager-*category", *actor, *userTypeIfDatamanager);
			if (*userTypeIfDatamanager == "normal" || *userTypeIfDatamanager == "manager") {
				*allowed = true;
				*reason = "Folder is *transitionTo by *actor from datamanager-*category";
			} else {
				*allowed = false;
				*reason = "Only a member of datamanager-*category is allowed to accept or reject a submitted folder";
				succeed;
			}
		} else {
			*allowed = true;
			*reason = "When no datamanager group exists, submitted folders are automatically accepted";
		}
	}

	if (*transitionTo == SECURED) {
		*allowed = false;
		*reason = "Only a rodsadmin is allowed to secure a folder to the vault";
		succeed;
	}

	if (*allowed) {
		iiGetLocks(*folder, *locks);
		if (size(*locks) > 0) {
			foreach(*rootCollection in *locks) {
				if (*rootCollection != *folder) {
					*allowed = false;
					*reason = "Found lock(s) starting from *rootCollection";
					break;
				}
			}
		}
	}
}


# \brief Check if a vault folder status transition is legal.
#
# \param[in] folder
# \param[in] transitionFrom  current status
# \param[in] transitionTo    status to transition to
# \param[in] actor           user name of actor requesting the transition
# \param[out] allowed        boolean to indicate if the action is allowed
# \param[out] reason         reason the action is not allowed
#
iiCanTransitionVaultStatus(*folder, *transitionFrom, *transitionTo, *actor, *allowed, *reason) {
	*allowed = false;
	*reason = "Unknown error";
	if (iiIsVaultStatusTransitionLegal(*transitionFrom, *transitionTo)) {
		*allowed = true;
		*reason = "Legal status transition. *transitionFrom -> *transitionTo";
	} else {
		*reason = "Illegal status transition. Current status is *transitionFrom.";
		succeed;
	}

	if (*transitionTo == PUBLISHED) {
		iiGetDOIFromMetadata(*folder, *yodaDOI);
		if (*yodaDOI == "") {
			*allowed = false;
			*reason = "*folder has no DOI"
			succeed;
		}

		iiGetLandingPageFromMetadata(*folder, *landingPage);
		if (*landingPage == "") {
			*allowed = false;
			*reason = "*folder has no landing page";
			succeed;
		}
	}
}