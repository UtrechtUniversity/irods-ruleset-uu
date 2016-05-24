# \file
# \brief File statistics functions
#			Functions in this file extract statistics from files
#			and collections
# \author Jan de Mooij
# \copyright Copyright (c) 2016, Utrecht university. All rights reserved
# \license GPLv3, see LICENSE
#


# \brief iiFileCount 		Obtain a count of all files in a collection
#
# \param[in] path 			The full path to a collection (not a file). This
#							is the COLL_NAME.	
# \param[out] totalSize 	Integer giving the sum of the size of all
#							the objects in the collection in bytes
# \param[out] dircount		The number of child directories in this collection
#							this number is determined recursively, so this does
#							include all subdirectories and not only those directly
#							under the given collection
# \param[out] filecount 	The total number of files in this collection. This
#							number is determined recursively, so this does include
#							all subfiles and not just those directly under the 
#							given collection.
# \param[out] locked 		Bool, true if and only if locked for vault or for snapshot.
#							If locked, a user can unlock, but can do nothing else until
#							unlocked.
# \param[out] frozen		Bool, true if and only if frozen for vault or for snapshot.
#							No user action can be taken on this object if this is true
#
iiFileCount(*path, *totalSize, *dircount, *filecount) {
	*direction = "forward";
	*ruleToProcess = "iiTreeFileCountRule";
	*buffer."dircount" = "0";
	*buffer."filecount" = "0";
	*buffer."totalSize" = "0";
	uuTreeWalk(*direction, *path, *ruleToProcess, *buffer, *error);
	*error = str(*error);
	*dircount = *buffer."dircount";
	*filecount = *buffer."filecount";
	*totalSize = *buffer."totalSize";
}

# \brief iiTreeFileCountRule Treewalk rule for the iiFileCount function. 
#							 Adds the correct values to the number of 
#							 directories, files, or total file size 
# 							 observed
#
# \param[in] itemParent 	 Parent collection of this item
# \param[in] itemName 		 name of this item
# \param[in] itemIsCollection Bool, true if and only if item is collection
# \param[in\out] buffer 	 The buffer, that contains key/values for dircount,
#							 filecount and size
# \param[out] error 		 Non-zero if an error occured
# 				
iiTreeFileCountRule(*itemParent, *itemName, *itemIsCollection, *buffer, *error) {
	*error = 0;
	if(*itemIsCollection) {
		*buffer."dircount" = str( int(*buffer."dircount") + 1);
	} else {
		*buffer."filecount" = str( int(*buffer."filecount") + 1);
		iiGetFileAttrs(*itemParent, *itemName, *size, *comment);
		*buffer."totalSize" = str( int(*buffer."totalSize") + int(*size));
	}
}

# \brief iiGetFileAttrs 	Obtain useful file attributes for the general intake,
#							such as item size, comment, and lock status
#
# \param[in] collectionName Name of parent collection of the to be observed item
# \param[in] fileName 		Filename of the to be observed item
# \param[out] size 			Integer giving size of file in bytes
# \param[out] comment 		string giving comments if they exist for this item
# \param[out] locked 		Bool, true if and only if locked for vault or for snapshot.
#							If locked, a user can unlock, but can do nothing else until
#							unlocked.
# \param[out] frozen		Bool, true if and only if frozen for vault or for snapshot.
#							No user action can be taken on this object if this is true
#
iiGetFileAttrs(*collectionName, *fileName, *size, *comment) {
	foreach(*row in SELECT DATA_SIZE, DATA_COMMENTS WHERE COLL_NAME = *collectionName AND DATA_NAME = *fileName) {
		*size = *row.DATA_SIZE;
		*comment = *row.DATA_COMMENTS;
	}
}
