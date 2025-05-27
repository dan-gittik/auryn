import auryn

auryn.execute(
    """
    %load filesystem
    dir/
        !for i in range(n):
            script_{i}.sh
                echo hello {i}!
            $ chmod +x script_{i}.sh
    """,
    n=3,
)