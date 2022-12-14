from django.core.exceptions import ValidationError
from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from .models import RawPic, ProcessedPic

import os
import datetime

from PIL import Image

import torch
from torchvision.transforms.functional import to_tensor, to_pil_image

from .api_models import Generator
from .serializers import RawSerializer, ProSerializer

torch.backends.cudnn.enabled = False
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.deterministic = True


class UploadImageViewSet(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        data1 = {
            'raw_pic': request.data.get('raw_pic'),
            'style': request.data.get('style'),
        }

        serializer = RawSerializer(data=data1)

        if serializer.is_valid():
            serializer.save()
            new_name, err = upload_handle(data1.get('raw_pic'), data1.get('style'))

            if err == 0:
                img = ProcessedPic.objects.get(pro_pic=('transfer/output/%s' % new_name))
                serializer_ = ProSerializer(img)
                return Response(serializer_.data, status=status.HTTP_200_OK)
            else:
                if err == 1:
                    data_ = {
                        'detail':
                            'TypeError: model must be paprika, celeba_distill, face_paint_512_v1, face_paint_512_v2.'
                    }
                if err == 2:
                    data_ = {
                        'detail': 'TypeError: type must be jpg, png, bmp or tiff.'
                    }
                return Response(data_, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# # Create your views here.
# def show_upload(request):
#     # model = request.POST.get("style")
#
#     return render(request, 'transfer/upload_pic.html')
#
#
def upload_handle(pic, model):
    # 1.?????????????????????????????????
    #     <input type = "file" name = "picture"> <br/>
    # pic: Img
    # pic = request.FILES.get("picture")
    # model = request.POST.get("style")
    err = 0
    new_name = ""
    if model not in ["paprika", "celeba_distill", "face_paint_512_v1", "face_paint_512_v2"]:
        err = 1
        return new_name, err

    model += '.pt'

    timestamp = datetime.datetime.strftime(datetime.datetime.now(), '%Y%m%d%H%M%S_')
    print(f"time is {timestamp}")
    new_name = timestamp + pic.name

    # 2.?????????????????????????????????
    # pic_path = '%s/transfer/input/%s' % (settings.MEDIA_ROOT, pic.name)
    # pic_path = '%s/transfer/input/%s' % (settings.MEDIA_ROOT, new_name)
    # input_dir = '%s/transfer/input' % settings.MEDIA_ROOT
    # output_dir = '%s/transfer/output' % settings.MEDIA_ROOT
    # weight_path = '%s/weights/%s' % (settings.STATIC_ROOT, model)
    pic_path = os.path.join(settings.MEDIA_ROOT,'transfer','input', new_name)
    input_dir = os.path.join(settings.MEDIA_ROOT, 'transfer', 'input')
    output_dir = os.path.join(settings.MEDIA_ROOT, 'transfer', 'output')
    weight_path = os.path.join(settings.STATIC_ROOT, 'weights', model)

    print(weight_path)

    with open(pic_path, 'wb') as f:
        for content in pic.chunks():
            f.write(content)

    # 3.?????????????????????????????????
    # RawPic.objects.create(raw_pic='transfer/input/%s' % pic.name)
    RawPic.objects.create(raw_pic='transfer/input/%s' % new_name)

    # 4.????????????
    device = 'cpu'

    # 5.????????????
    net = Generator()
    net.load_state_dict(torch.load(weight_path, map_location="cpu"))
    net.to(device).eval()
    print(f"model loaded: {weight_path}")

    os.makedirs(output_dir, exist_ok=True)

    # ???input????????????????????????????????????
    # for pic.name in sorted(os.listdir(input_dir)):

    # ???????????????????????????
    if os.path.splitext(new_name)[-1].lower() not in [".jpg", ".png", ".bmp", ".tiff"]:
        # raise ValidationError("TypeError: type must be jpg, png, bmp or tiff")
        err = 2
        return new_name, err
    # ??????
    raw_image = Image.open(os.path.join(input_dir, new_name)).convert("RGB")
    image = load_image(os.path.join(input_dir, new_name), raw_image.size[0] > 1000)

    # ???????????????core???
    with torch.no_grad():
        image = to_tensor(image).unsqueeze(0) * 2 - 1
        out = net(image.to(device), False).cpu()
        out = out.squeeze(0).clip(-1, 1) * 0.5 + 0.5
        out = to_pil_image(out)

    # test
    # out = image
    # print(f"processed image size is {image.size}")

    # ??????????????????output??????
    out.save(os.path.join(output_dir, new_name))

    # ??????????????????????????????
    ProcessedPic.objects.create(pro_pic='transfer/output/%s' % new_name)

    print(f"image saved: {new_name}")

    # pic_transfer(args)
    # return render(request, 'transfer/download_pic.html', {"pic": new_name})
    # return render(request, 'transfer/test.html',{"pic": 'FHuDYCNWQAwoMpo.jpg'})
    return new_name, err


# ??????????????????
def load_image(image_path, x32):
    img = Image.open(image_path).convert("RGB")

    # if x32:
    #     def to_32s(x):
    #         return 256 if x < 256 else x - x % 32
    #
    #     w, h = img.size
    #     img = img.resize((to_32s(w), to_32s(h)))
    if x32:
        base_width = 1000
        ratio = (base_width / float(img.size[0]))
        hsize = int((float(img.size[1]) * float(ratio)))
        img = img.resize((base_width, hsize), Image.ANTIALIAS)

    return img

# # ????????????
# def download(request):
#     # ????????????????????????
#     # filepath = request.GET.get("photo")  # ???????????????  imgs/aa.png
#     # filename = filepath[filepath.rindex("/") + 1:]  # ???????????????????????????
#     # path = os.path.join(os.getcwd(), "media", filepath.replace("/", "\\"))
#     # print(path)
#
#     pic_name = request.GET.get("photo")
#     # print(pic_name)
#     pic_path = '%s/transfer/output/%s' % (settings.MEDIA_ROOT, pic_name)
#
#     with open(pic_path, "rb") as fr:
#         response = HttpResponse(fr.read())
#         response["Content-Type"] = "image/png"
#         response["Content-Disposition"] = "attachment;filename=" + pic_name
#     return response
#
#     # file = open(pic_path, 'rb')
#     # response = HttpResponse(fr.read())
#     # response['Content-Type'] = 'img/png'  # ????????????????????????????????????????????????
#     # response['Content-Disposition'] = 'attachment;filename=pic_name'
#     # return response
#
#
# def test(request):
#     # img_path = '%s/transfer/output/%s' % (settings.MEDIA_ROOT, 'FHuDYCNWQAwoMpo.jpg')
#     # img = Image.open(img_path)
#     # print(img_path)
#     return render(request, 'transfer/test.html', {"pic": 'FHuDYCNWQAwoMpo.jpg'})
#
#
# def error_500(request):
#     return render(request, "error/error_500.html", status=500)
