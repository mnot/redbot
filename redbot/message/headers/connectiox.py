
description = u"""\
The `%(field_name)s` field usually means that a HTTP load balancer, proxy or other intermediary in
front of the server has rewritten the `Connection` header, to allow it to insert its own.

Usually, this is done so that clients won't see `Connection: close` so that the connection can be
reused.

It takes this form because the most efficient way of assuring that clients don't see the header is
to rearrange or change individual characters in its name.

"""