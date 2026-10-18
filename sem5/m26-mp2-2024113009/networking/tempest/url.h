#ifndef URL_H
#define URL_H

#include <stddef.h>
//following rfc 3986 as that's what rfc 9112 points to

char *url_encode(const char *src);

#endif

