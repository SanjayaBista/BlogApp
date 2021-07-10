from typing import ContextManager
from django.shortcuts import render
from django.shortcuts import render, get_object_or_404
from .models import Post, Comment
from django.core.paginator import Paginator, EmptyPage,PageNotAnInteger
from django.views.generic import ListView
from .forms import EmailPostForm, CommentForm
from django.core.mail import send_mail
from taggit.models import Tag
from django.db.models import Count
from django.contrib.postgres.search import SearchVector
from .forms import EmailPostForm, CommentForm, SearchForm
from django.contrib.postgres.search import SearchVector, SearchQuery,SearchRank
from django.contrib.postgres.search import TrigramSimilarity


class PostListView(ListView):
    queryset = Post.published.all()
    context_object_name = 'posts'
    paginate_by = 3
    template_name = 'post/list.html'


def post_list(request, tag_slug=None):
    posts = Post.published.all()
    object_list = Post.published.all()
    tag = None
    if tag_slug:
        tag = get_object_or_404(Tag,slug=tag_slug)
        object_list = object_list.filter(tags__in=[tag])
    paginator = Paginator(object_list, 3) # 3 posts in each page
    page = request.GET.get('page')
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer deliver the first page
        posts = paginator.page(1)
    except EmptyPage:
        # If page is out of range deliver last page of results
        posts = paginator.page(paginator.num_pages)
    context = {'posts': posts,'page':page,'tag':tag}
    return render(request,'post/list.html',context)


def post_detail(request, year, month, day, post):
    post = get_object_or_404(Post, slug=post,
                             status='published',
                             publish__year=year,
                             publish__month=month,
                             publish__day=day)
     #active comments in the post
    comments = post.comments.filter(active=True)
    new_comment = None
    if request.method == 'POST':
        # comment posted
        comment_form = CommentForm(data=request.POST)
        if comment_form.is_valid():
            #create obj but dont save to database yet
            new_comment = comment_form.save(commit=False)
            #assign the current post to comment
            new_comment.post = post
            #save the comment to db
            new_comment.save()
    else:
        comment_form = CommentForm()
    #similar post list
    post_tags_ids = post.tags.values_list('id', flat=True)
    similar_posts = Post.published.filter(tags__in=post_tags_ids).exclude(id=post.id)
    context = {'post': post,'comments':comments,'new_comment':new_comment,'comment_form':comment_form,'similar_posts':similar_posts}
    similar_posts = similar_posts.annotate(same_tags=Count('tags')).order_by('-same_tags','-publish')[:4]
    return render(request,'post/detail.html',context)


# def post_share(request,post_id):
#     # Retrieve post by id
#     post = get_object_or_404(Post, id=post_id, status='published')
#     if request.method == 'POST':
#     # Form was submitted
#         form = EmailPostForm(request.POST)
#         if form.is_valid():
#         # Form fields passed validation
#             cd = form.cleaned_data
#     else:
#         form = EmailPostForm()
#     context = {'post': post,'form': form}
#     return render(request, 'blog/post/share.html', context)

def post_share(request,post_id):
    # Retrieve post by id
    post = get_object_or_404(Post, id=post_id, status='published')
    sent = False
    if request.method == 'POST':
    # Form was submitted
        form = EmailPostForm(request.POST)
        if form.is_valid():
        # Form fields passed validation
            cd = form.cleaned_data
            post_url = request.build_absolute_uri(post.get_absolute_url())
            subject = f"{cd['name']} recommends you read"f"{post.title}"
            message = f"Read {post.title} at {post_url}\n\n"f"{cd['name']}\'s comments: {cd['comments']}"
            send_mail = (subject,message,'sanjaybista681@gmail.com',[cd['to']])
            sent = True
    else:
        form = EmailPostForm()
    context = {'post': post,'form': form,'sent':sent}
    return render(request, 'post/share.html', context)


def post_search(request):
    form = SearchForm()
    query = None
    results = []
    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            #Building search view
            # results = Post.published.annotate(search=SearchVector('title','body'),).filter(search=query)

            #Stemming and ranking results
            # search_vector = SearchVector('title','body')
            # search_query = SearchQuery(query)
            # results = Post.published.annotate(search=search_vector,rank=SearchRank(search_vector,search_query)).filter(search=search_query).order_by('-rank')

            # Weighting queries
            search_vector = SearchVector('title', weight='A') + \
            SearchVector('body', weight='B')
            search_query = SearchQuery(query)
            # results = Post.published.annotate(rank=SearchRank(search_vector, search_query)).filter(rank__gte=0.3).order_by('-rank')

            # Searching with trigram similarity
            results = Post.published.annotate(similarity=TrigramSimilarity('title', query),).filter(similarity__gt=0.1).order_by('-similarity')
    return render(request,'post/search.html',{'form': form,'query': query,'results': results})