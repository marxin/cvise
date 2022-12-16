//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013, 2014, 2015, 2016, 2017, 2018 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#if HAVE_CONFIG_H
#  include <config.h>
#endif

#include "RemoveBaseClass.h"

#include "TransformationManager.h"

static const char* DescriptionMsg =
"This pass merges a base class into a derived class if \n\
  * it has less than or equal to 5 declarations. \n\
All its declarations will be moved into one of its subclasses, \
and all references to this base class will be replaced with \
the corresponding subclass. \n";

static RegisterTransformation<RemoveBaseClass, RemoveBaseClass::EMode>
         Trans("merge-base-class", DescriptionMsg, RemoveBaseClass::EMode::Merge);


// Implementation is in RemoveBaseClass.cp

