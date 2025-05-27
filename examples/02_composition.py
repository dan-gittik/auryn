import auryn

output = auryn.execute(
    """
        %extend 02a_base.aur
        %define head
            <title>{title}</title>
            %include 02b_meta.aur
        %define body
            <p>{message}</p>
    """,
    title="Auryn",
    author="Dan Gittik",
    description="The Auryn metaprogramming engine",
    message="Metaprogramming is cool!",
)
print(output)