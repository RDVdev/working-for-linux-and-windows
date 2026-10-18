#ifndef LOGGER_H
#define LOGGER_H

#include <stdbool.h>

void logger_init(bool enabled); 

void logger_log(const char *fmt, ...); //just found out i can do this in c like *args in python :)

void logger_close(void);


#endif