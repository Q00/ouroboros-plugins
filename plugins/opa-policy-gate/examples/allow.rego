package example

import rego.v1

default allow := false

allow if {
  input.user == "alice"
  data.roles[input.user] == "admin"
}
