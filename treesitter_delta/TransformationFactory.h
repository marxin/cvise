#ifndef TRANSFORMATION_FACTORY_H
#define TRANSFORMATION_FACTORY_H

#include <memory>
#include <string>

#include "Transformation.h"

std::unique_ptr<Transformation> createTransformation(const std::string &Name);

#endif
