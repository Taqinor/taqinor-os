import tokenize, io, bisect, sys
p=sys.argv[1]; deb=int(sys.argv[2]); fin=int(sys.argv[3])
t=open(p,encoding='utf-8').read()
l=[j.start[0] for j in tokenize.generate_tokens(io.StringIO(t).readline) if j.type==tokenize.NEWLINE]
print(p,deb,fin,bisect.bisect_right(l,fin)-bisect.bisect_left(l,deb))
