# README

1. Maintain a README.md, everytime where there is a code change, make sure the readme.md is up to date. 
2. README.md should contain the intruction for launch the system in a running state.
3. The file should also provide instruction for testing.

# Logging

1. Logging should be provided in different levels, using the -v, -vv, -vvv convention.
2. By default, log should be preserved in a file called `logs/log_YYYYMMDD_HHMMSS.log`, the file pattern should be put into gitignore file. timestamp of the log should be the local date time.

# Check in
1. Everytime one an agent operation is done, it should be checked in to a breach called `wip/YYYYMMDD_HHMMSS/<underscored separated summary>` time stamp of the branch should be the UTC time.
2. Never check into main.

# Test
1. Always include test and implement the core module in a way that is test able.
2. Every time before a coding job is done, run tests to ensure all test passes.
3. Every time when a new components is implemented, add test for it.