import auryn


output = auryn.execute("""
    !for i in range(n):
        line {i}
""", n=3)
print(output)