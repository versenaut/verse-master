/*
 * A simple example program, showing how to use the verse_ms module.
*/

#include <stdio.h>
#include <stdlib.h>

#include "verse.h"
#include "verse_ms.h"

/* This gets called when we receive a ping from the master server. */
static void cb_ping(void *user, const char *address, const char *message)
{
	VMSServer	**s;
	unsigned int	i, j;

	/* Attempt to parse the message, as a master server response. */
	if((s = verse_ms_list_parse(message)) != NULL)
	{
		/* Go through results, print IP and all fields for each. */
		for(i = 0; s[i] != NULL; i++)
		{
			printf("%s\n", s[i]->ip);
			for(j = 0; j < s[i]->num_fields; j++)
				printf(" %s = '%s'\n",
				       s[i]->field[j].name,
				       s[i]->field[j].value);
		}
		free(s);	/* Free the server info. */
	}
}

int main(int argc, char *argv[])
{
	int	i;

	/* Register a callback to run when ping is received. */
	verse_callback_set((void *) verse_send_ping, (void *) cb_ping, NULL);

	/* Ping all master servers named on the command line. */
	for(i = 1; argv[i] != NULL; i++)
		verse_ms_get_send(argv[i], VERSE_MS_FIELD_DESCRIPTION, NULL);

	/* Spend forever just waiting for replies. */
	while(1)
	{
		verse_callback_update(10000);
	}

	return EXIT_SUCCESS;
}
